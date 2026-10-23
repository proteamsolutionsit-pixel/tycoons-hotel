"""Staff authentication: Argon2id, legacy bcrypt upgrade, server-side
sessions (idle/absolute expiry, revocation), CSRF binding, password reset."""
import re
from datetime import timedelta

import bcrypt
from fastapi.testclient import TestClient

from app.core.security import hash_password, password_problems, verify_password
from app.core.timeutil import utcnow
from app.main import app
from app.models import AdminSession, AdminUser, AuditLog
from app.services import auth_service
from tests.conftest import ADMIN_PW, login

ADMIN = "admin@tycoons.example.com"


def _user(db, email=ADMIN) -> AdminUser:
    db.expire_all()
    return db.query(AdminUser).filter_by(email=email).one()


def test_passwords_are_argon2id():
    h = hash_password("Correct-Horse-Battery-9")
    assert h.startswith("$argon2id$")
    assert verify_password("Correct-Horse-Battery-9", h)
    assert not verify_password("correct-horse-battery-9", h)


def test_legacy_bcrypt_hash_still_works_and_is_upgraded_on_login(client, db):
    user = _user(db)
    user.password_hash = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
    db.commit()
    login(client)
    assert _user(db).password_hash.startswith("$argon2id$")
    client.cookies.clear()
    login(client)  # the upgraded hash verifies too


def test_password_policy_rejects_common_and_personal_passwords():
    assert password_problems("Password12345")            # common word
    assert password_problems("Tycoons-Hotel-2026")       # hotel name
    assert password_problems("Asharao-Secure-99", email="asharao@example.com")
    assert password_problems("aaaaaaaaaaA1")             # little variety
    assert password_problems("short1A")
    assert not password_problems("Velvet-Monsoon-482")


def test_session_token_is_opaque_and_only_its_hash_is_stored(client, db):
    login(client)
    token = client.cookies.get("tyc_admin")
    assert len(token) >= 40 and token.count(".") == 0  # not a JWT
    row = db.query(AdminSession).one()
    assert row.token_hash != token and len(row.token_hash) == 64


def test_idle_timeout_ends_session(client, db, settings):
    login(client)
    s = db.query(AdminSession).one()
    s.last_seen_at = utcnow() - timedelta(minutes=settings.session_idle_minutes + 1)
    db.commit()
    r = client.get("/api/v1/admin/auth/me")
    assert r.status_code == 401
    db.expire_all()
    assert db.query(AdminSession).one().revoked_reason == "idle"


def test_activity_keeps_session_alive(client, db, settings):
    login(client)
    s = db.query(AdminSession).one()
    s.last_seen_at = utcnow() - timedelta(minutes=settings.session_idle_minutes - 1)
    db.commit()
    assert client.get("/api/v1/admin/auth/me").status_code == 200
    db.expire_all()
    assert utcnow() - db.query(AdminSession).one().last_seen_at < timedelta(minutes=1)


def test_absolute_lifetime_ends_session(client, db):
    login(client)
    s = db.query(AdminSession).one()
    s.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_logout_revokes_only_that_session(client, db):
    other = TestClient(app)
    h1 = login(client)
    login(other)
    assert client.post("/api/v1/admin/auth/logout", headers=h1).status_code == 200
    assert client.get("/api/v1/admin/auth/me").status_code == 401
    assert other.get("/api/v1/admin/auth/me").status_code == 200


def test_csrf_token_is_bound_to_its_session(client):
    other = TestClient(app)
    login(client)
    h_other = login(other)
    # session A's cookie with session B's (valid) CSRF token is refused
    r = client.patch("/api/v1/admin/room-types/1", json={"sort_order": 5}, headers=h_other)
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"


def test_password_change_signs_out_other_sessions_but_not_this_one(client):
    other = TestClient(app)
    h = login(client)
    login(other)
    r = client.post("/api/v1/admin/auth/change-password", headers=h,
                    json={"current_password": ADMIN_PW, "new_password": "Velvet-Monsoon-482"})  # pragma: allowlist secret
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/admin/auth/me").status_code == 200
    assert other.get("/api/v1/admin/auth/me").status_code == 401


def test_deactivating_a_user_ends_their_sessions(client, db):
    staff = TestClient(app)
    login(staff, "staff@tycoons.example.com", "Staff-Password-123")
    h = login(client)
    staff_id = _user(db, "staff@tycoons.example.com").id
    assert client.patch(f"/api/v1/admin/users/{staff_id}", json={"is_active": False}, headers=h).status_code == 200
    assert staff.get("/api/v1/admin/auth/me").status_code == 401


def test_password_reset_flow(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_service, "send_mail", lambda to, subject, body: sent.append((to, body)))
    other = TestClient(app)
    login(other)

    r = client.post("/api/v1/admin/auth/password-reset/request", json={"email": ADMIN})
    unknown = client.post("/api/v1/admin/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert r.status_code == unknown.status_code == 202
    assert r.json() == unknown.json()  # no account enumeration
    assert len(sent) == 1 and sent[0][0] == ADMIN
    token = re.search(r"#token=([\w-]+)", sent[0][1]).group(1)

    weak = client.post("/api/v1/admin/auth/password-reset/confirm", json={"token": token, "new_password": "password1234"})
    assert weak.status_code == 400 and weak.json()["error"]["code"] == "weak_password"
    ok = client.post("/api/v1/admin/auth/password-reset/confirm", json={"token": token, "new_password": "Velvet-Monsoon-482"})
    assert ok.status_code == 200
    again = client.post("/api/v1/admin/auth/password-reset/confirm", json={"token": token, "new_password": "Velvet-Monsoon-483"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_reset_token"
    assert other.get("/api/v1/admin/auth/me").status_code == 401   # existing sessions ended
    login(client, ADMIN, "Velvet-Monsoon-482")


def test_expired_reset_token_is_rejected(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_service, "send_mail", lambda to, subject, body: sent.append(body))
    client.post("/api/v1/admin/auth/password-reset/request", json={"email": ADMIN})
    token = re.search(r"#token=([\w-]+)", sent[0]).group(1)
    from app.models import PasswordResetToken
    row = db.query(PasswordResetToken).one()
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    r = client.post("/api/v1/admin/auth/password-reset/confirm", json={"token": token, "new_password": "Velvet-Monsoon-482"})
    assert r.status_code == 400


def test_failed_logins_are_audited_without_the_password(client, db):
    client.post("/api/v1/admin/auth/login", json={"email": ADMIN, "password": "Wrong-Guess-123"})  # pragma: allowlist secret
    row = db.query(AuditLog).filter_by(action="auth.login_failed").one()
    assert row.outcome == "failure" and row.actor_email == ADMIN
    assert "Wrong-Guess" not in str(row.details)


def test_login_rate_limited_per_account_across_ips(client, settings):
    settings.rate_limit_enabled = True
    try:
        codes = [client.post("/api/v1/admin/auth/login", json={"email": ADMIN, "password": "x"}).status_code
                 for _ in range(6)]
    finally:
        settings.rate_limit_enabled = False
    assert codes[:5] == [401] * 5 and codes[5] == 429
