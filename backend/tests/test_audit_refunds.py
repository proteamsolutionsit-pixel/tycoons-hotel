"""Audit trail, refund authorisation/eligibility, external refunds, booking
terms, payment-review resolution and webhook payload redaction."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.models import AuditLog, Booking, Payment, PaymentEvent, SiteSetting
from app.models.enums import BookingStatus, PaymentStatus
from tests.conftest import STAFF_PW, FakeGateway, create_booking, login


def _paid_booking(client, gateway, **kw):
    res = create_booking(client, **kw)
    order_id = res["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    r = client.post("/api/v1/payments/verify", json={"razorpay_order_id": order_id, "razorpay_payment_id": pay["id"],
                                                     "razorpay_signature": FakeGateway.sign(order_id, pay["id"])})
    assert r.json()["booking"]["status"] == "confirmed"
    return res, pay


def test_rate_change_is_audited_with_before_and_after(client, admin_headers, db):
    client.patch("/api/v1/admin/room-types/2", json={"base_rate_paise": 820000}, headers=admin_headers)
    row = db.query(AuditLog).filter_by(action="room_type.update").one()
    assert row.details["changes"]["base_rate_paise"] == {"from": 750000, "to": 820000}
    assert row.actor_email == "admin@tycoons.example.com" and row.request_id


def test_failed_change_leaves_no_audit_record(client, admin_headers, db):
    r = client.patch("/api/v1/admin/room-types/1", json={"name": "Premium Room"}, headers=admin_headers)  # duplicate
    assert r.status_code == 409
    assert db.query(AuditLog).filter_by(action="room_type.update").count() == 0


def test_audit_log_is_append_only_in_the_database(client, admin_headers, db):
    triggers = db.execute(text("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = DATABASE() "
                               "AND event_object_table = 'audit_logs'")).scalar()
    if triggers < 2:
        pytest.skip("audit_logs triggers not installed (creating them needs SUPER with binary logging); "
                    "append-only then relies on the runtime account's INSERT/SELECT-only grant")
    client.patch("/api/v1/admin/room-types/2", json={"sort_order": 9}, headers=admin_headers)
    with pytest.raises(OperationalError, match="append-only"):
        db.execute(text("UPDATE audit_logs SET action = 'tampered'"))
    db.rollback()
    with pytest.raises(OperationalError, match="append-only"):
        db.execute(text("DELETE FROM audit_logs"))
    db.rollback()


def test_audit_log_view_is_admin_only(client, admin_headers):
    client.patch("/api/v1/admin/room-types/2", json={"sort_order": 9}, headers=admin_headers)
    page = client.get("/api/v1/admin/audit-logs", params={"action": "room_type"}).json()
    assert page["total"] == 1
    client.cookies.clear()
    login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.get("/api/v1/admin/audit-logs").status_code == 403


def test_refund_requires_amount_confirmation(client, gateway, admin_headers, db):
    _paid_booking(client, gateway)
    bid = db.query(Booking).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel", json={"reason": "Guest request", "refund": True},
                    headers=admin_headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == "refund_amount_unconfirmed"
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel",
                    json={"reason": "Guest request", "refund": True, "confirm_refund_paise": 100}, headers=admin_headers)
    assert r.status_code == 400
    assert "refund_payment" not in gateway.calls
    db.expire_all()
    assert db.query(Booking).one().status == BookingStatus.CONFIRMED


def test_staff_cannot_refund(client, gateway, db):
    _paid_booking(client, gateway)
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    bid = db.query(Booking).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel",
                    json={"reason": "Guest request", "refund": True, "confirm_refund_paise": 1500000}, headers=headers)
    assert r.status_code == 403
    assert "refund_payment" not in gateway.calls


def test_refund_is_audited_and_cannot_repeat(client, gateway, admin_headers, db):
    _paid_booking(client, gateway)
    bid = db.query(Booking).one().id
    body = {"reason": "Guest request", "refund": True, "confirm_refund_paise": 1500000}
    assert client.post(f"/api/v1/admin/bookings/{bid}/cancel", json=body, headers=admin_headers).status_code == 200
    again = client.post(f"/api/v1/admin/bookings/{bid}/cancel", json=body, headers=admin_headers)
    assert again.status_code == 409
    assert gateway.calls.count("refund_payment") == 1
    row = db.query(AuditLog).filter_by(action="booking.cancel").one()
    assert row.details["refund"] is True and row.details["refund_id"].startswith("rfnd_")
    events = [e.event_type for e in db.query(PaymentEvent).order_by(PaymentEvent.id)]
    assert events.index("refund.requested") < events.index("refund.created")  # intent recorded first


def test_refund_with_nothing_captured_is_rejected(client, gateway, admin_headers, db):
    create_booking(client)
    bid = db.query(Booking).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel",
                    json={"reason": "Guest request", "refund": True, "confirm_refund_paise": 1500000}, headers=admin_headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == "nothing_to_refund"


def test_external_refund_on_active_booking_raises_an_alert(client, gateway, admin_headers, db):
    res, pay = _paid_booking(client, gateway)
    body, headers = FakeGateway.webhook("refund.processed", refund={"id": "rfnd_dash123456", "payment_id": pay["id"],
                                                                     "amount": 1500000, "status": "processed"})
    r = client.post("/api/v1/payments/webhook", content=body, headers=headers)
    assert "refunded_while_booking_active" in r.json()["result"]
    db.expire_all()
    assert db.query(Payment).one().status == PaymentStatus.REFUNDED
    assert client.get("/api/v1/admin/dashboard").json()["alerts"]["refunded_active_booking"] == 1


def test_webhook_payload_is_stored_without_customer_details(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    pay.update({"email": "asha@example.com", "contact": "+919845012345", "vpa": "asha@okbank",
                "card": {"last4": "1111", "network": "Visa"}, "notes": {"booking_reference": "x"}})
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    client.post("/api/v1/payments/webhook", content=body, headers=headers)
    stored = str(db.query(PaymentEvent).filter_by(source="webhook").one().payload)
    for secret in ("asha@example.com", "9845012345", "okbank", "1111", "Visa"):
        assert secret not in stored
    assert pay["id"] in stored and "captured" in stored


def test_booking_records_terms_and_policy_snapshot(client, gateway, db):
    db.get(SiteSetting, "cancellation_policy").value = "Free cancellation until 48 hours before arrival."
    db.get(SiteSetting, "booking_terms_version").value = "2026-11"
    db.commit()
    create_booking(client)
    # a later policy change does not alter what this guest agreed to
    db.get(SiteSetting, "cancellation_policy").value = "Non-refundable."
    db.commit()
    db.expire_all()
    b = db.query(Booking).one()
    assert b.terms_version == "2026-11" and b.terms_accepted_at is not None
    assert b.cancellation_policy == "Free cancellation until 48 hours before arrival."


def test_payment_review_can_be_confirmed_once_a_room_is_free(client, gateway, admin_headers, db):
    from datetime import timedelta

    from app.core.timeutil import utcnow
    first = create_booking(client, room="tycoon-suite")
    b = db.query(Booking).one()
    b.hold_expires_at = utcnow() - timedelta(minutes=5)
    db.commit()
    for email in ("x@example.com", "y@example.com"):
        o = create_booking(client, room="tycoon-suite", guest_email=email)["checkout"]["order_id"]
        p = gateway.pay(o)
        client.post("/api/v1/payments/verify", json={"razorpay_order_id": o, "razorpay_payment_id": p["id"],
                                                     "razorpay_signature": FakeGateway.sign(o, p["id"])})
    pay = gateway.pay(first["checkout"]["order_id"])
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    client.post("/api/v1/payments/webhook", content=body, headers=headers)
    db.expire_all()
    late = db.query(Booking).filter_by(reference=first["booking"]["reference"]).one()
    assert late.status == BookingStatus.PAYMENT_REVIEW

    r = client.post(f"/api/v1/admin/bookings/{late.id}/confirm", json={"note": "Upgraded"}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"
    client.patch("/api/v1/admin/room-types/4", json={"total_rooms": 3}, headers=admin_headers)
    r = client.post(f"/api/v1/admin/bookings/{late.id}/confirm", json={"note": "Opened a third suite"},
                    headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert db.query(AuditLog).filter_by(action="booking.confirm_review").count() == 1
