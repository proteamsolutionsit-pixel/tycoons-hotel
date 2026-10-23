import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models import Booking, Payment
from app.models.enums import BookingStatus
from tests.conftest import KEY_SECRET, WEBHOOK_SECRET, booking_payload, create_booking


def test_create_booking_holds_room_and_creates_order(client, gateway, db):
    r = client.post("/api/bookings", json=booking_payload(nights=3))
    assert r.status_code == 201
    body = r.json()
    b, co = body["booking"], body["checkout"]
    assert b["status"] == "pending_payment" and b["reference"].startswith("TYC")
    assert b["total_paise"] == 3 * 750000
    assert co["amount"] == b["total_paise"] and co["key_id"] == "rzp_test_fake"
    assert co["order_id"] in gateway.orders
    assert gateway.orders[co["order_id"]]["receipt"] == b["reference"]
    # secrets never leave the server
    assert KEY_SECRET not in r.text and WEBHOOK_SECRET not in r.text

    row = db.execute(select(Booking).where(Booking.reference == b["reference"])).unique().scalar_one()
    assert row.hold_expires_at > utcnow()


def test_client_supplied_amount_is_ignored(client, gateway):
    r = client.post("/api/bookings", json=booking_payload(total_paise=100, nightly_rate_paise=1, amount=1))
    assert r.status_code == 201
    assert r.json()["checkout"]["amount"] == 2 * 750000


def test_validation_errors_are_field_level(client, gateway):
    r = client.post("/api/bookings", json=booking_payload(guest_email="nope", guest_phone="12", accept_terms=False))
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"guest_email", "guest_phone", "accept_terms"} <= fields


def test_idempotency_key_prevents_duplicate_bookings(client, gateway, db):
    key = str(uuid.uuid4())
    r1 = client.post("/api/bookings", json=booking_payload(), headers={"Idempotency-Key": key})
    r2 = client.post("/api/bookings", json=booking_payload(), headers={"Idempotency-Key": key})
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["booking"]["reference"] == r2.json()["booking"]["reference"]
    assert r1.json()["checkout"]["order_id"] == r2.json()["checkout"]["order_id"]
    assert gateway.calls.count("create_order") == 1
    assert db.query(Booking).count() == 1


def test_idempotency_key_reused_for_different_booking_is_rejected(client, gateway):
    key = str(uuid.uuid4())
    client.post("/api/bookings", json=booking_payload(), headers={"Idempotency-Key": key})
    r = client.post("/api/bookings", json=booking_payload(room="deluxe-room"), headers={"Idempotency-Key": key})
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_mismatch"


def test_last_room_cannot_be_sold_twice(client, gateway):
    # The Tycoon Suite has 2 rooms in the seed data
    create_booking(client, room="tycoon-suite")
    create_booking(client, room="tycoon-suite", guest_email="b@example.com")
    r = client.post("/api/bookings", json=booking_payload(room="tycoon-suite", guest_email="c@example.com"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"
    # A stay starting on the day the others check out is fine
    create_booking(client, room="tycoon-suite", days_ahead=12, guest_email="d@example.com")


def test_lapsed_hold_releases_inventory(client, gateway, db):
    create_booking(client, room="tycoon-suite")
    create_booking(client, room="tycoon-suite", guest_email="b@example.com")
    for b in db.query(Booking).all():
        b.hold_expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    create_booking(client, room="tycoon-suite", guest_email="c@example.com")
    db.expire_all()
    assert db.query(Booking).filter(Booking.status == BookingStatus.EXPIRED).count() == 2


def test_order_failure_releases_the_hold(client, gateway, db):
    gateway.fail_create = True
    r = client.post("/api/bookings", json=booking_payload(room="tycoon-suite"))
    assert r.status_code == 502 and r.json()["error"]["code"] == "payment_order_failed"
    b = db.query(Booking).one()
    assert b.status == BookingStatus.CANCELLED
    gateway.fail_create = False
    create_booking(client, room="tycoon-suite")
    create_booking(client, room="tycoon-suite", guest_email="b@example.com")


def test_payments_unavailable_without_keys(client):
    from app.main import app
    from app.services.razorpay_gateway import get_gateway
    app.dependency_overrides[get_gateway] = lambda: None
    r = client.post("/api/bookings", json=booking_payload())
    assert r.status_code == 503 and r.json()["error"]["code"] == "payments_unavailable"


def test_party_must_fit_room(client, gateway):
    r = client.post("/api/bookings", json=booking_payload(adults=3))
    assert r.status_code == 400 and r.json()["error"]["code"] == "party_too_large"


def test_lookup_requires_matching_email(client, gateway):
    ref = create_booking(client)["booking"]["reference"]
    ok = client.post("/api/bookings/lookup", json={"reference": ref.lower(), "email": "ASHA@example.com"})
    assert ok.status_code == 200 and ok.json()["reference"] == ref
    bad = client.post("/api/bookings/lookup", json={"reference": ref, "email": "someone@example.com"})
    missing = client.post("/api/bookings/lookup", json={"reference": "TYCZZZZZZZZ", "email": "asha@example.com"})
    assert bad.status_code == missing.status_code == 404
    assert bad.json()["error"]["message"] == missing.json()["error"]["message"]


def test_retry_payment_reuses_order(client, gateway):
    first = create_booking(client)
    ref = first["booking"]["reference"]
    r = client.post(f"/api/bookings/{ref}/payment", json={"reference": ref, "email": "asha@example.com"})
    assert r.status_code == 200
    assert r.json()["checkout"]["order_id"] == first["checkout"]["order_id"]
    assert gateway.calls.count("create_order") == 1


def test_retry_payment_after_expiry_is_refused(client, gateway, db):
    ref = create_booking(client)["booking"]["reference"]
    b = db.query(Booking).one()
    b.hold_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    r = client.post(f"/api/bookings/{ref}/payment", json={"reference": ref, "email": "asha@example.com"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "booking_expired"
    assert client.post("/api/bookings/lookup",
                       json={"reference": ref, "email": "asha@example.com"}).json()["status"] == "expired"


def test_payment_row_stores_order_not_card_data(client, gateway, db):
    create_booking(client)
    p = db.query(Payment).one()
    cols = {c.name for c in Payment.__table__.columns}
    assert not cols & {"card_number", "cvv", "card"}
    assert p.razorpay_order_id.startswith("order_") and p.status.value == "created"
