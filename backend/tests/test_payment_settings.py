"""Admin > Payment gateway: switching between test payments and Razorpay, and
entering Razorpay keys from the admin. Secrets are stored encrypted, never
returned or logged, and the change is audited."""
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from razorpay.errors import BadRequestError

from app.core import secretbox
from app.main import app
from app.models import AuditLog, PaymentGatewaySettings
from app.services import payment_settings_service
from app.services.razorpay_gateway import GatewayError, RazorpayGateway, gateway_for
from tests.conftest import KEY_SECRET, STAFF_PW, booking_payload, login

URL = "/api/v1/admin/payment-settings"
NEW_KEY_ID = "rzp_test_AbCdEf1234567890"
NEW_SECRET = "NewSecretValue1234567890"  # pragma: allowlist secret
NEW_WEBHOOK = "new-webhook-secret-123"  # pragma: allowlist secret
LIVE_KEY_ID = "rzp_live_ZyXwVu0987654321"


@pytest.fixture
def rclient():
    """No gateway override: requests resolve the gateway from the saved settings."""
    with TestClient(app) as c:
        yield c


def _save(client, headers, **body):
    data = {"mode": "razorpay", "key_id": NEW_KEY_ID, "key_secret": NEW_SECRET, "webhook_secret": NEW_WEBHOOK, **body}
    return client.put(URL, json=data, headers=headers)


def _current(db):
    db.expire_all()
    return payment_settings_service.load(db)


def test_staff_cannot_see_or_change_gateway_settings(rclient):
    headers = login(rclient, "staff@tycoons.example.com", STAFF_PW)
    assert rclient.get(URL).status_code == 403
    assert _save(rclient, headers).status_code == 403
    assert rclient.post(URL + "/test", json={}, headers=headers).status_code == 403


def test_view_reports_environment_config_without_secrets(rclient):
    login(rclient)
    r = rclient.get(URL)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "environment" and body["mode"] == "razorpay" and body["active"] == "test"
    assert body["key_id"] == "rzp_test_fake" and body["has_key_secret"] and body["has_webhook_secret"]
    assert body["webhook_url"].endswith("/api/v1/payments/webhook")
    assert KEY_SECRET not in r.text


def test_saving_keys_encrypts_them_and_switches_the_gateway(rclient, db):
    headers = login(rclient)
    r = _save(rclient, headers)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "admin" and r.json()["key_id"] == NEW_KEY_ID
    assert NEW_SECRET not in r.text and NEW_WEBHOOK not in r.text

    row = db.get(PaymentGatewaySettings, 1)
    assert NEW_SECRET not in (row.key_secret_enc or "") and NEW_WEBHOOK not in (row.webhook_secret_enc or "")
    cfg = _current(db)
    assert (cfg.key_id, cfg.key_secret, cfg.webhook_secret) == (NEW_KEY_ID, NEW_SECRET, NEW_WEBHOOK)
    gw = gateway_for(cfg)
    assert isinstance(gw, RazorpayGateway) and gw.key_id == NEW_KEY_ID

    # Webhooks are now checked with the new secret, and the old one is refused
    body = b'{"event":"payment.captured"}'
    assert gw.verify_webhook_signature(body, hmac.new(NEW_WEBHOOK.encode(), body, hashlib.sha256).hexdigest())
    assert not gw.verify_webhook_signature(body, hmac.new(b"test_webhook_secret_456", body, hashlib.sha256).hexdigest())

    entry = db.query(AuditLog).filter_by(action="payment_settings.update").one()
    assert entry.details["key_id"] == {"from": "rzp_test_fake", "to": NEW_KEY_ID}
    assert entry.details["replaced"] == {"api_key": True, "webhook_key": True}
    assert NEW_SECRET not in str(entry.details) and NEW_WEBHOOK not in str(entry.details)


def test_blank_secrets_keep_the_stored_ones(rclient, db):
    headers = login(rclient)
    assert _save(rclient, headers).status_code == 200
    r = _save(rclient, headers, key_secret="", webhook_secret=None)
    assert r.status_code == 200, r.text
    cfg = _current(db)
    assert cfg.key_secret == NEW_SECRET and cfg.webhook_secret == NEW_WEBHOOK


def test_a_new_key_id_needs_its_own_secret(rclient):
    headers = login(rclient)
    assert _save(rclient, headers).status_code == 200
    r = _save(rclient, headers, key_id="rzp_test_Other1234567890", key_secret="")
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "key_secret"


@pytest.mark.parametrize("key_id", ["", "pk_test_123456789", "rzp_test_short", "rzp_test_bad chars!!"])
def test_malformed_key_id_is_rejected(rclient, key_id):
    headers = login(rclient)
    r = _save(rclient, headers, key_id=key_id)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "key_id"


def test_switching_to_live_keys_needs_explicit_confirmation(rclient, db):
    headers = login(rclient)
    r = _save(rclient, headers, key_id=LIVE_KEY_ID)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "confirm_live"
    assert db.get(PaymentGatewaySettings, 1) is None
    r = _save(rclient, headers, key_id=LIVE_KEY_ID, confirm_live=True)
    assert r.status_code == 200 and r.json()["active"] == "live"


def test_test_payment_mode_can_be_chosen_in_the_admin(rclient, db):
    headers = login(rclient)
    r = rclient.put(URL, json={"mode": "mock"}, headers=headers)
    assert r.status_code == 200 and r.json()["active"] == "mock"
    # Razorpay keys are kept for switching back
    assert _current(db).key_secret == KEY_SECRET
    co = rclient.post("/api/v1/bookings", json=booking_payload()).json()["checkout"]
    assert co["mode"] == "mock" and co["key_id"] == "rzp_test_mock"


def test_test_payments_cannot_be_chosen_in_production(rclient, db, settings):
    headers = login(rclient)
    settings.environment = "production"
    try:
        r = rclient.put(URL, json={"mode": "mock"}, headers=headers)
        assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "mode"
        # and a stored mock row is ignored there: payments are off, not fake
        db.add(PaymentGatewaySettings(id=1, mode="mock", key_id=""))
        db.commit()
        assert gateway_for(_current(db)) is None
    finally:
        settings.environment = "test"


def test_reset_returns_to_the_environment(rclient, db):
    headers = login(rclient)
    assert _save(rclient, headers).status_code == 200
    r = rclient.delete(URL, headers=headers)
    assert r.status_code == 200 and r.json()["source"] == "environment" and r.json()["key_id"] == "rzp_test_fake"
    assert db.query(AuditLog).filter_by(action="payment_settings.reset").count() == 1


def test_changes_require_the_csrf_token(rclient):
    login(rclient)
    assert _save(rclient, {}).status_code == 403


def test_lost_encryption_key_fails_closed(rclient, db, monkeypatch):
    headers = login(rclient)
    assert _save(rclient, headers).status_code == 200
    monkeypatch.setattr(secretbox, "_fernet", __import__("cryptography.fernet").fernet.Fernet(
        __import__("cryptography.fernet").fernet.Fernet.generate_key()))
    cfg = _current(db)
    assert not cfg.secrets_readable and gateway_for(cfg) is None
    assert rclient.get(URL).json()["secrets_readable"] is False


def test_connection_check_reports_rejected_keys(rclient, monkeypatch):
    headers = login(rclient)

    def refuse(self):
        try:
            raise BadRequestError("Authentication failed")
        except BadRequestError as exc:
            raise GatewayError("order.all") from exc
    monkeypatch.setattr(RazorpayGateway, "check_credentials", refuse)
    r = rclient.post(URL + "/test", json={"key_id": NEW_KEY_ID, "key_secret": NEW_SECRET}, headers=headers)
    assert r.status_code == 200 and r.json()["ok"] is False and "rejected" in r.json()["message"]

    monkeypatch.setattr(RazorpayGateway, "check_credentials", lambda self: None)
    r = rclient.post(URL + "/test", json={}, headers=headers)   # saved (environment) keys
    assert r.json() == {"ok": True, "message": "Connected to Razorpay (test mode)."}
