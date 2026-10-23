"""Test payment mode (PAYMENT_MODE=mock): bookings can be completed without a
Razorpay account, through the same verification code, and the mode can
never be enabled in production."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models import AuditLog, Booking, Payment
from app.models.enums import BookingStatus, PaymentStatus
from tests.conftest import booking_payload


@pytest.fixture
def mock_mode(settings):
    settings.payment_mode = "mock"
    yield
    settings.payment_mode = "razorpay"


@pytest.fixture
def mclient(mock_mode):
    # no gateway override: get_gateway() itself must pick the mock gateway
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def _book(client):
    r = client.post("/api/v1/bookings", json=booking_payload())
    assert r.status_code == 201, r.text
    return r.json()


def test_checkout_config_announces_mock_mode(mclient):
    co = _book(mclient)["checkout"]
    assert co["mode"] == "mock" and co["key_id"] == "rzp_test_mock"
    assert co["order_id"].startswith("order_mock") and co["amount"] == 1500000


def test_successful_test_payment_confirms_through_real_verification(mclient, db):
    co = _book(mclient)["checkout"]
    resp = mclient.post("/api/v1/payments/mock/checkout", json={"razorpay_order_id": co["order_id"], "outcome": "success"})
    assert resp.status_code == 200
    signed = resp.json()
    assert set(signed) == {"razorpay_order_id", "razorpay_payment_id", "razorpay_signature"}
    r = mclient.post("/api/v1/payments/verify", json=signed)
    assert r.status_code == 200 and r.json()["booking"]["status"] == "confirmed"
    db.expire_all()
    p = db.query(Payment).one()
    assert p.status == PaymentStatus.CAPTURED and p.signature_verified and p.method == "test"


def test_forged_signature_is_still_rejected_in_mock_mode(mclient, db):
    co = _book(mclient)["checkout"]
    signed = mclient.post("/api/v1/payments/mock/checkout",
                          json={"razorpay_order_id": co["order_id"], "outcome": "success"}).json()
    signed["razorpay_signature"] = "0" * 64
    assert mclient.post("/api/v1/payments/verify", json=signed).status_code == 400
    db.expire_all()
    assert db.query(Booking).one().status == BookingStatus.PENDING_PAYMENT


def test_failed_test_payment_then_retry(mclient, db):
    co = _book(mclient)["checkout"]
    fail = mclient.post("/api/v1/payments/mock/checkout", json={"razorpay_order_id": co["order_id"], "outcome": "failure"})
    assert fail.status_code == 200 and fail.json()["error"]["code"] == "BAD_REQUEST_ERROR"
    db.expire_all()
    assert db.query(Payment).one().status == PaymentStatus.FAILED
    assert db.query(Booking).one().status == BookingStatus.PENDING_PAYMENT
    ok = mclient.post("/api/v1/payments/mock/checkout", json={"razorpay_order_id": co["order_id"], "outcome": "success"})
    assert mclient.post("/api/v1/payments/verify", json=ok.json()).json()["booking"]["status"] == "confirmed"


def test_admin_refund_and_reconcile_work_in_mock_mode(mclient, db):
    from tests.conftest import login
    co = _book(mclient)["checkout"]
    signed = mclient.post("/api/v1/payments/mock/checkout",
                          json={"razorpay_order_id": co["order_id"], "outcome": "success"}).json()
    mclient.post("/api/v1/payments/verify", json=signed)
    headers = login(mclient)
    bid = db.query(Booking).one().id
    pid = db.query(Payment).one().id
    assert mclient.post(f"/api/v1/admin/payments/{pid}/reconcile", headers=headers).status_code == 200
    r = mclient.post(f"/api/v1/admin/bookings/{bid}/cancel", headers=headers,
                     json={"reason": "Testing refund", "refund": True, "confirm_refund_paise": 1500000})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    db.expire_all()
    assert db.query(Payment).one().status == PaymentStatus.REFUNDED
    assert db.query(AuditLog).filter_by(action="booking.cancel").count() == 1


def test_expired_hold_cannot_be_paid(mclient, db):
    from datetime import timedelta

    from app.core.timeutil import utcnow
    co = _book(mclient)["checkout"]
    b = db.query(Booking).one()
    b.hold_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    r = mclient.post("/api/v1/payments/mock/checkout", json={"razorpay_order_id": co["order_id"], "outcome": "success"})
    assert r.status_code == 409


def test_mock_endpoint_does_not_exist_with_real_razorpay(client, gateway):
    co = client.post("/api/v1/bookings", json=booking_payload()).json()["checkout"]
    assert co["mode"] == "razorpay"
    r = client.post("/api/v1/payments/mock/checkout", json={"razorpay_order_id": co["order_id"], "outcome": "success"})
    assert r.status_code == 404


def test_production_refuses_mock_mode():
    with pytest.raises(ValidationError, match="PAYMENT_MODE must be razorpay"):
        Settings(environment="production", payment_mode="mock", razorpay_key_id="k", razorpay_key_secret="s",
                 razorpay_webhook_secret="w", cookie_secure=True, allowed_hosts="hotel.example",
                 public_base_url="https://hotel.example", _env_file=None)
