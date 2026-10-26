"""Test setup.

Tests run against a real MySQL database (TEST_DATABASE_URL, default the
`tycoons_test` database created by scripts/mysql-init.ps1). The schema is built
by running the Alembic migrations, so the migrations are tested too. Each test
starts from freshly seeded data.

Razorpay is replaced by FakeGateway: network calls are simulated in memory,
but signature verification is the real SDK code with test secrets.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
_env = dotenv_values(BACKEND / ".env")
TEST_DB = os.environ.get("TEST_DATABASE_URL") or _env.get("TEST_DATABASE_URL")
if not TEST_DB:
    raise RuntimeError("Set TEST_DATABASE_URL (see backend/.env.example)")

KEY_SECRET = "test_key_secret_123"  # pragma: allowlist secret
WEBHOOK_SECRET = "test_webhook_secret_456"  # pragma: allowlist secret
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": TEST_DB,
    "RAZORPAY_KEY_ID": "rzp_test_fake",
    "RAZORPAY_KEY_SECRET": KEY_SECRET,
    "RAZORPAY_WEBHOOK_SECRET": WEBHOOK_SECRET,
    "PAYMENT_MODE": "razorpay",          # a developer's .env may say mock
    "RATE_LIMIT_ENABLED": "false",
    "RATE_LIMIT_BACKEND": "database",
    "LOG_JSON": "false",
    "LOG_LEVEL": "WARNING",
    "STORAGE_DIR": str(BACKEND / ".pytest-storage"),
    "SMTP_HOST": "",
})

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.timeutil import hotel_today  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser, Role  # noqa: E402
from app.models.enums import AdminRole  # noqa: E402
from app.seed import seed  # noqa: E402
from app.services.razorpay_gateway import GatewayError, RazorpayGateway, get_gateway  # noqa: E402

ADMIN_PW = "Admin-Password-123"
STAFF_PW = "Staff-Password-123"


class FakeGateway(RazorpayGateway):
    def __init__(self) -> None:
        super().__init__("rzp_test_fake", KEY_SECRET, WEBHOOK_SECRET)
        self.orders: dict[str, dict] = {}
        self.payments: dict[str, dict] = {}
        self.calls: list[str] = []
        self.fail_create = False
        self.fail_fetch = False
        self.fail_refund = False
        self.auto_capture = True

    # simulated API -------------------------------------------------------
    def create_order(self, *, amount, currency, receipt, notes):
        self.calls.append("create_order")
        if self.fail_create:
            raise GatewayError("order.create")
        oid = "order_" + secrets.token_hex(7)
        self.orders[oid] = {"id": oid, "amount": amount, "currency": currency, "receipt": receipt,
                            "notes": notes, "status": "created"}
        return dict(self.orders[oid])

    def fetch_payment(self, payment_id):
        self.calls.append("fetch_payment")
        if self.fail_fetch:
            raise GatewayError("payment.fetch")
        return dict(self.payments[payment_id])

    def fetch_order_payments(self, order_id):
        self.calls.append("fetch_order_payments")
        return [dict(p) for p in self.payments.values() if p["order_id"] == order_id]

    def capture_payment(self, payment_id, amount, currency):
        self.calls.append("capture_payment")
        p = self.payments[payment_id]
        p["status"] = "captured"
        return dict(p)

    def refund_payment(self, payment_id, amount, notes):
        self.calls.append("refund_payment")
        if self.fail_refund:
            raise GatewayError("payment.refund")
        self.payments[payment_id]["status"] = "refunded"
        return {"id": "rfnd_" + secrets.token_hex(6), "status": "processed", "amount": amount}

    # helpers for tests ----------------------------------------------------
    def pay(self, order_id: str, status: str | None = None, amount: int | None = None) -> dict:
        order = self.orders[order_id]
        pid = "pay_" + secrets.token_hex(7)
        status = status or ("captured" if self.auto_capture else "authorized")
        self.payments[pid] = {"id": pid, "order_id": order_id, "amount": amount or order["amount"],
                              "currency": order["currency"], "status": status, "method": "upi",
                              "error_code": "BAD_REQUEST_ERROR" if status == "failed" else None,
                              "error_description": "Payment failed" if status == "failed" else None}
        return dict(self.payments[pid])

    @staticmethod
    def sign(order_id: str, payment_id: str) -> str:
        return hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def webhook(event: str, payment: dict | None = None, order: dict | None = None,
                refund: dict | None = None) -> tuple[bytes, dict]:
        payload = {}
        if payment is not None:
            payload["payment"] = {"entity": payment}
        if order is not None:
            payload["order"] = {"entity": order}
        if refund is not None:
            payload["refund"] = {"entity": refund}
        body = json.dumps({"entity": "event", "event": event, "payload": payload}).encode()
        sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return body, {"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_" + uuid.uuid4().hex[:20],
                      "Content-Type": "application/json"}


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.cmd_opts = type("o", (), {"x": [f"url={TEST_DB}"]})()
    return cfg


def _alembic_upgrade() -> None:
    command.upgrade(_alembic_config(), "head")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in list(Base.metadata.tables) + ["alembic_version"]:
            conn.execute(text(f"DROP TABLE IF EXISTS `{t}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    _alembic_upgrade()
    yield


@pytest.fixture(autouse=True)
def _fresh_data(_schema):
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in Base.metadata.tables:
            conn.execute(text(f"TRUNCATE TABLE `{t}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    with SessionLocal() as db:
        seed(db)   # also creates the built-in Administrator / Front desk roles
        roles = {r.key: r.id for r in db.query(Role).all()}
        db.add_all([
            AdminUser(email="admin@tycoons.example.com", full_name="Test Admin", role=AdminRole.ADMIN,
                      role_id=roles["administrator"], password_hash=hash_password(ADMIN_PW)),
            AdminUser(email="staff@tycoons.example.com", full_name="Test Staff", role=AdminRole.STAFF,
                      role_id=roles["front_desk"], password_hash=hash_password(STAFF_PW)),
        ])
        db.commit()
    limiter.reset()
    yield


@pytest.fixture
def gateway():
    fake = FakeGateway()
    app.dependency_overrides[get_gateway] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_gateway, None)


@pytest.fixture
def client(gateway):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def login(client: TestClient, email: str = "admin@tycoons.example.com", password: str = ADMIN_PW) -> dict:
    r = client.post("/api/v1/admin/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": client.cookies.get("tyc_csrf")}


@pytest.fixture
def admin_headers(client):
    return login(client)


def stay(days_ahead: int = 10, nights: int = 2) -> dict:
    ci = hotel_today() + timedelta(days=days_ahead)
    return {"check_in": ci.isoformat(), "check_out": (ci + timedelta(days=nights)).isoformat()}


def booking_payload(room: str = "premium-room", days_ahead: int = 10, nights: int = 2, **over) -> dict:
    data = {**stay(days_ahead, nights), "adults": 2, "children": 0, "room_type_slug": room,
            "guest_name": "Asha Rao", "guest_email": "asha@example.com", "guest_phone": "+91 98450 12345",
            "special_requests": "Late arrival", "accept_terms": True}
    data.update(over)
    return data


def create_booking(client: TestClient, **kw) -> dict:
    r = client.post("/api/v1/bookings", json=booking_payload(**kw))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def settings():
    return get_settings()
