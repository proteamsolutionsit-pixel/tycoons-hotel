"""API versioning, request limits, host checks, health, the shared rate
limiter, the state machine, dashboard figures and the migration round-trip."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, text

from alembic import command
from app.core.rate_limit import DatabaseLimiter
from app.core.timeutil import hotel_today
from app.db.session import engine
from app.domain.states import BOOKING_TRANSITIONS, IllegalTransition, move_booking, move_payment
from app.models import Booking, Payment
from app.models.enums import BookingStatus as B
from app.models.enums import PaymentStatus as P
from tests.conftest import FakeGateway, _alembic_config, create_booking

# -- versioning ----------------------------------------------------------------

def test_v1_is_current_and_legacy_paths_still_work(client):
    v1 = client.get("/api/v1/rooms")
    legacy = client.get("/api/rooms")
    assert v1.status_code == legacy.status_code == 200
    assert v1.json() == legacy.json()
    assert "deprecation" not in v1.headers
    assert legacy.headers["deprecation"] == "true" and "/api/v1/rooms" in legacy.headers["link"]


def test_legacy_webhook_path_still_processes_events(client, gateway, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    body, headers = FakeGateway.webhook("payment.captured", payment=gateway.pay(order_id))
    assert client.post("/api/payments/webhook", content=body, headers=headers).status_code == 200
    db.expire_all()
    assert db.query(Booking).one().status == B.CONFIRMED


def test_openapi_documents_only_v1(client):
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert paths and all(p.startswith("/api/v1/") for p in paths)
    assert "/api/v1/admin/audit-logs" in paths


# -- request limits / hosts / headers -------------------------------------------

def test_oversized_json_body_is_rejected(client):
    r = client.post("/api/v1/enquiries/contact", content=b'{"x":"' + b"a" * (1024 * 1024 + 10) + b'"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "request_too_large"


def test_oversized_upload_is_rejected_before_parsing(client, settings):
    big = b"%PDF-" + b"0" * (settings.max_upload_body_bytes + 10)
    r = client.post("/api/v1/careers/applications", data={"name": "Kiran Das"}, files={"cv": ("cv.pdf", big)})
    assert r.status_code == 413


def test_unknown_host_header_is_rejected(client):
    assert client.get("/api/v1/rooms", headers={"Host": "evil.example"}).status_code == 400


def test_security_headers_and_request_id(client):
    r = client.get("/api/v1/rooms", headers={"X-Request-ID": "trace-abc-12345"})
    assert r.headers["x-request-id"] == "trace-abc-12345"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_errors_never_leak_internals(monkeypatch):
    from app.api.routes import public

    def boom(*a, **k):
        raise RuntimeError("SELECT secret FROM users -- G:\\path\\file.py")
    monkeypatch.setattr(public, "select", boom)
    from fastapi.testclient import TestClient

    from app.main import app
    r = TestClient(app, raise_server_exceptions=False).get("/api/v1/rooms")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "SELECT" not in r.text and "path" not in r.text and r.json()["error"]["request_id"]


# -- health --------------------------------------------------------------------

def test_health_endpoints(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


# -- shared rate limiter --------------------------------------------------------

def test_database_rate_limiter_is_shared_and_atomic():
    lim = DatabaseLimiter()
    lim.reset()
    # 20 concurrent hits from "different workers" against a limit of 7
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: lim.hit("test|shared", 7, 60), range(20)))
    assert results.count(None) == 7
    assert all(r is not None and r > 0 for r in results if r is not None)


def test_rate_limit_window_resets(db):
    lim = DatabaseLimiter()
    lim.reset()
    assert lim.hit("test|reset", 1, 60) is None
    assert lim.hit("test|reset", 1, 60) is not None
    with engine.begin() as conn:  # age the window
        conn.execute(text("UPDATE rate_limit_buckets SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 SECOND"))
    assert lim.hit("test|reset", 1, 60) is None


def test_booking_lookup_limited_per_reference(client, gateway, settings):
    ref = create_booking(client)["booking"]["reference"]
    settings.rate_limit_enabled = True
    try:
        codes = [client.post("/api/v1/bookings/lookup", json={"reference": ref, "email": f"guess{i}@example.com"}).status_code
                 for i in range(11)]
    finally:
        settings.rate_limit_enabled = False
    assert codes[:10] == [404] * 10 and codes[10] == 429


# -- state machine ----------------------------------------------------------------

@pytest.mark.parametrize("start,end", [(B.CONFIRMED, B.PENDING_PAYMENT), (B.CANCELLED, B.CONFIRMED),
                                       (B.EXPIRED, B.CANCELLED), (B.CONFIRMED, B.EXPIRED)])
def test_illegal_booking_transitions_raise(start, end):
    with pytest.raises(IllegalTransition):
        move_booking(Booking(reference="TYCTEST", status=start), end)


@pytest.mark.parametrize("start,end", [(P.CAPTURED, P.FAILED), (P.REFUNDED, P.CAPTURED), (P.CAPTURED, P.CREATED),
                                       (P.AUTHORIZED, P.CREATED)])
def test_illegal_payment_transitions_raise(start, end):
    with pytest.raises(IllegalTransition):
        move_payment(Payment(razorpay_order_id="order_x", status=start), end)


def test_every_booking_state_is_covered():
    assert set(BOOKING_TRANSITIONS) == set(B)
    assert move_booking(Booking(reference="T", status=B.PENDING_PAYMENT), B.CONFIRMED) is True
    assert move_booking(Booking(reference="T", status=B.CONFIRMED), B.CONFIRMED) is False


# -- dashboard / occupancy -----------------------------------------------------------

def test_dashboard_occupancy_uses_real_bookings(client, gateway, admin_headers, db):
    res = create_booking(client, room="tycoon-suite", days_ahead=0, nights=2)
    order_id = res["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    client.post("/api/v1/payments/verify", json={"razorpay_order_id": order_id, "razorpay_payment_id": pay["id"],
                                                 "razorpay_signature": FakeGateway.sign(order_id, pay["id"])})
    d = client.get("/api/v1/admin/dashboard").json()
    assert d["rooms_total"] == 40 and d["rooms_sold_tonight"] == 1 and d["occupancy_tonight_pct"] == 2.5
    assert d["arrivals_today"] == 1 and d["revenue_30d_paise"] == 3200000
    occ = client.get("/api/v1/admin/occupancy", params={"start": hotel_today().isoformat(), "days": 3}).json()
    suite = next(r for r in occ["rooms"] if r["slug"] == "tycoon-suite")
    assert suite["booked"] == [1, 1, 0] and suite["total_rooms"] == 2


def test_admin_lists_sort_and_paginate(client, gateway, admin_headers):
    for i, room in enumerate(["twin-room", "deluxe-room", "premium-room"]):
        create_booking(client, room=room, guest_email=f"g{i}@example.com")
    page = client.get("/api/v1/admin/bookings", params={"sort": "total", "order": "asc", "limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert [i["total_paise"] for i in page["items"]] == [1300000, 1500000]
    assert client.get("/api/v1/admin/bookings", params={"sort": "password_hash"}).status_code == 422


# -- migrations --------------------------------------------------------------------

def test_migration_downgrade_and_upgrade_round_trip():
    """Runs last-ish: rebuilds the test schema through downgrade/upgrade."""
    cfg = _alembic_config()
    command.downgrade(cfg, "8f2012434e2d")  # pragma: allowlist secret
    cols = {c["name"] for c in inspect(engine).get_columns("bookings")}
    assert "terms_version" not in cols and not inspect(engine).has_table("audit_logs")
    command.upgrade(cfg, "head")
    assert inspect(engine).has_table("audit_logs")
    with engine.connect() as conn:
        triggers = conn.execute(text("SELECT trigger_name FROM information_schema.triggers "
                                     "WHERE trigger_schema = DATABASE()")).scalars().all()
    assert set(triggers) == {"audit_logs_no_update", "audit_logs_no_delete"}

