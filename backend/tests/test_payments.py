from datetime import timedelta

from app.core.timeutil import utcnow
from app.models import Booking, Payment, PaymentEvent
from app.models.enums import BookingStatus, PaymentStatus
from tests.conftest import FakeGateway, create_booking


def _verify(client, order_id, payment_id, signature=None):
    return client.post("/api/payments/verify", json={
        "razorpay_order_id": order_id, "razorpay_payment_id": payment_id,
        "razorpay_signature": signature or FakeGateway.sign(order_id, payment_id)})


def _state(db):
    db.expire_all()
    return db.query(Booking).one(), db.query(Payment).one()


def test_verified_captured_payment_confirms_booking(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    r = _verify(client, order_id, pay["id"])
    assert r.status_code == 200
    assert r.json()["booking"]["status"] == "confirmed"
    b, p = _state(db)
    assert b.status == BookingStatus.CONFIRMED and b.confirmed_at and b.hold_expires_at is None
    assert p.status == PaymentStatus.CAPTURED and p.signature_verified and p.razorpay_payment_id == pay["id"]


def test_invalid_signature_never_marks_paid(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    r = _verify(client, order_id, pay["id"], signature="0" * 64)
    assert r.status_code == 400 and r.json()["error"]["code"] == "payment_verification_failed"
    b, p = _state(db)
    assert b.status == BookingStatus.PENDING_PAYMENT and p.status == PaymentStatus.CREATED
    assert not p.signature_verified
    assert db.query(PaymentEvent).filter_by(result="invalid_signature").count() == 1


def test_signature_for_another_payment_is_rejected(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    sig_for_other = FakeGateway.sign(order_id, "pay_somethingelse1")
    assert _verify(client, order_id, pay["id"], sig_for_other).status_code == 400
    assert _state(db)[0].status == BookingStatus.PENDING_PAYMENT


def test_valid_signature_but_failed_payment_does_not_confirm(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id, status="failed")
    r = _verify(client, order_id, pay["id"])
    assert r.json()["booking"]["status"] == "pending_payment"
    assert _state(db)[1].status == PaymentStatus.FAILED


def test_amount_mismatch_does_not_confirm(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id, amount=100)
    _verify(client, order_id, pay["id"])
    b, p = _state(db)
    assert b.status == BookingStatus.PENDING_PAYMENT and p.status != PaymentStatus.CAPTURED


def test_repeated_verification_is_idempotent(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    assert _verify(client, order_id, pay["id"]).json()["booking"]["status"] == "confirmed"
    first_confirmed = _state(db)[0].confirmed_at
    again = _verify(client, order_id, pay["id"])
    assert again.status_code == 200 and again.json()["booking"]["status"] == "confirmed"
    assert _state(db)[0].confirmed_at == first_confirmed


def test_authorized_payment_is_captured_then_confirmed(client, gateway, db):
    gateway.auto_capture = False
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    assert pay["status"] == "authorized"
    assert _verify(client, order_id, pay["id"]).json()["booking"]["status"] == "confirmed"
    assert "capture_payment" in gateway.calls


def test_fetch_failure_waits_for_webhook(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    gateway.fail_fetch = True
    r = _verify(client, order_id, pay["id"])
    assert r.status_code == 200 and r.json()["booking"]["status"] == "pending_payment"
    assert _state(db)[1].status == PaymentStatus.AUTHORIZED

    body, headers = FakeGateway.webhook("payment.captured", payment=gateway.payments[pay["id"]])
    assert client.post("/api/payments/webhook", content=body, headers=headers).status_code == 200
    b, p = _state(db)
    assert b.status == BookingStatus.CONFIRMED and p.status == PaymentStatus.CAPTURED


def test_webhook_rejects_bad_signature(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    headers["X-Razorpay-Signature"] = "f" * 64
    r = client.post("/api/payments/webhook", content=body, headers=headers)
    assert r.status_code == 400
    assert _state(db)[0].status == BookingStatus.PENDING_PAYMENT


def test_webhook_signature_covers_raw_body(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    tampered = body.replace(b'"upi"', b'"card"')  # same JSON meaning, different bytes
    assert client.post("/api/payments/webhook", content=tampered, headers=headers).status_code == 400


def test_duplicate_webhook_is_processed_once(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    r1 = client.post("/api/payments/webhook", content=body, headers=headers)
    r2 = client.post("/api/payments/webhook", content=body, headers=headers)
    assert r1.status_code == r2.status_code == 200
    assert r2.json()["result"] == "duplicate"
    assert db.query(PaymentEvent).filter_by(source="webhook").count() == 1
    assert _state(db)[0].status == BookingStatus.CONFIRMED


def test_order_paid_webhook_confirms(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    body, headers = FakeGateway.webhook("order.paid", payment=pay, order=gateway.orders[order_id])
    client.post("/api/payments/webhook", content=body, headers=headers)
    assert _state(db)[0].status == BookingStatus.CONFIRMED


def test_late_failure_event_cannot_undo_capture(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    good = gateway.pay(order_id)
    _verify(client, order_id, good["id"])
    failed = gateway.pay(order_id, status="failed")
    body, headers = FakeGateway.webhook("payment.failed", payment=failed)
    client.post("/api/payments/webhook", content=body, headers=headers)
    b, p = _state(db)
    assert b.status == BookingStatus.CONFIRMED and p.status == PaymentStatus.CAPTURED


def test_failed_attempt_then_successful_retry(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    failed = gateway.pay(order_id, status="failed")
    body, headers = FakeGateway.webhook("payment.failed", payment=failed)
    client.post("/api/payments/webhook", content=body, headers=headers)
    b, p = _state(db)
    assert b.status == BookingStatus.PENDING_PAYMENT and p.status == PaymentStatus.FAILED
    assert p.error_code == "BAD_REQUEST_ERROR"

    ok = gateway.pay(order_id)
    assert _verify(client, order_id, ok["id"]).json()["booking"]["status"] == "confirmed"


def test_capture_after_hold_lapsed_confirms_if_room_free(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    b = db.query(Booking).one()
    b.hold_expires_at = utcnow() - timedelta(minutes=5)
    b.status = BookingStatus.EXPIRED
    db.commit()
    pay = gateway.pay(order_id)
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    r = client.post("/api/payments/webhook", content=body, headers=headers)
    assert "confirmed_after_hold_lapsed" in r.json()["result"]
    assert _state(db)[0].status == BookingStatus.CONFIRMED


def test_capture_after_hold_lapsed_and_room_gone_needs_review(client, gateway, db):
    first = create_booking(client, room="tycoon-suite")
    b = db.query(Booking).one()
    b.hold_expires_at = utcnow() - timedelta(minutes=5)
    db.commit()
    # both suites are sold to other guests meanwhile
    for email in ("x@example.com", "y@example.com"):
        o = create_booking(client, room="tycoon-suite", guest_email=email)["checkout"]["order_id"]
        p = gateway.pay(o)
        _verify(client, o, p["id"])

    pay = gateway.pay(first["checkout"]["order_id"])
    body, headers = FakeGateway.webhook("payment.captured", payment=pay)
    client.post("/api/payments/webhook", content=body, headers=headers)
    db.expire_all()
    late = db.query(Booking).filter_by(reference=first["booking"]["reference"]).one()
    assert late.status == BookingStatus.PAYMENT_REVIEW
    assert db.query(Booking).filter_by(status=BookingStatus.CONFIRMED).count() == 2


def test_unknown_order_webhook_is_acknowledged(client, gateway, db):
    body, headers = FakeGateway.webhook("payment.captured", payment={
        "id": "pay_unknown1234", "order_id": "order_notours1234", "amount": 100, "currency": "INR"})
    r = client.post("/api/payments/webhook", content=body, headers=headers)
    assert r.status_code == 200
    assert db.query(PaymentEvent).one().result == "unknown_order"


def test_client_report_does_not_change_status(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    r = client.post("/api/payments/report", json={"razorpay_order_id": order_id, "outcome": "dismissed"})
    assert r.status_code == 202
    b, p = _state(db)
    assert b.status == BookingStatus.PENDING_PAYMENT and p.status == PaymentStatus.CREATED


def test_unverified_pending_booking_stays_unpaid(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    gateway.pay(order_id)  # money moved at Razorpay, but nothing verified reached us
    b, p = _state(db)
    assert b.status == BookingStatus.PENDING_PAYMENT and p.status == PaymentStatus.CREATED


def test_malformed_verify_payload_rejected(client, gateway):
    r = client.post("/api/payments/verify", json={"razorpay_order_id": "x", "razorpay_payment_id": "y",
                                                   "razorpay_signature": "z"})
    assert r.status_code == 422
