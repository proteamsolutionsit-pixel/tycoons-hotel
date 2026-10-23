"""Staff authentication: sign-in, server-side sessions, password change and
email-based password reset.

Sessions: the browser holds an opaque 256-bit token (HttpOnly cookie); the DB
stores only its SHA-256 plus the hash of the session's CSRF token. A session
ends after SESSION_IDLE_MINUTES without activity or SESSION_ABSOLUTE_HOURS in
total, on logout, on password change/reset, on role change or deactivation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from fastapi import BackgroundTasks, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, Unauthorized
from app.core.rate_limit import client_ip
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    new_token,
    password_problems,
    sha256_hex,
    verify_password,
)
from app.core.timeutil import utcnow
from app.models import AdminSession, AdminUser, PasswordResetToken
from app.services import audit
from app.services.mailer import send_mail

log = logging.getLogger("app.auth")
# Refresh last_seen_at at most this often, so every request is not a write.
_TOUCH_EVERY = timedelta(seconds=60)


@dataclass
class IssuedSession:
    user: AdminUser
    session: AdminSession
    token: str
    csrf: str


def _check_new_password(user: AdminUser, password: str, field: str) -> None:
    if problems := password_problems(password, email=user.email, name=user.full_name):
        raise AppError("Password needs " + ", ".join(problems) + ".", code="weak_password",
                       details=[{"field": field, "message": "Needs " + ", ".join(problems)}])


def start_session(db: Session, user: AdminUser, request: Request | None) -> IssuedSession:
    s = get_settings()
    token, csrf = new_token(), new_token()
    now = utcnow()
    session = AdminSession(
        user_id=user.id, token_hash=sha256_hex(token), csrf_hash=sha256_hex(csrf), created_at=now, last_seen_at=now,
        expires_at=now + timedelta(hours=s.session_absolute_hours),
        ip=client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
    )
    db.add(session)
    db.flush()
    return IssuedSession(user=user, session=session, token=token, csrf=csrf)


def login(db: Session, email: str, password: str, request: Request) -> IssuedSession:
    email = email.strip().lower()
    user = db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none()
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        reason = "unknown_email" if not user else ("inactive" if ok else "bad_password")
        audit.record_now(action="auth.login_failed", outcome="failure", actor_type="anonymous", actor_email=email,
                         resource_type="admin_user", resource_id=user.id if user else None,
                         details={"reason": reason}, request=request)
        log.warning("Admin login failed", extra={"reason": reason})
        raise Unauthorized("Incorrect email or password.", code="invalid_credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)  # bcrypt -> Argon2id, or stronger Argon2 params
    user.last_login_at = utcnow()
    issued = start_session(db, user, request)
    audit.record(db, action="auth.login", actor=user, resource_type="admin_user", resource_id=user.id, request=request)
    db.commit()
    return issued


def authenticate(db: Session, token: str) -> tuple[AdminUser, AdminSession] | None:
    """Resolve a session cookie to (user, session), enforcing every expiry rule."""
    if not token or len(token) > 100:
        return None
    s = get_settings()
    session = db.execute(select(AdminSession).where(AdminSession.token_hash == sha256_hex(token))).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None
    now = utcnow()
    if now >= session.expires_at:
        _revoke(session, "expired")
        db.commit()
        return None
    if now - session.last_seen_at > timedelta(minutes=s.session_idle_minutes):
        _revoke(session, "idle")
        db.commit()
        return None
    user = db.get(AdminUser, session.user_id)
    if user is None or not user.is_active:
        _revoke(session, "user_inactive")
        db.commit()
        return None
    if now - session.last_seen_at >= _TOUCH_EVERY:
        session.last_seen_at = now
        db.commit()
    return user, session


def _revoke(session: AdminSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoked_reason = reason[:40]


def revoke_all(db: Session, user_id: int, reason: str, *, except_session_id: int | None = None) -> int:
    stmt = (update(AdminSession)
            .where(AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None))
            .values(revoked_at=utcnow(), revoked_reason=reason[:40])
            .execution_options(synchronize_session=False))
    if except_session_id is not None:
        stmt = stmt.where(AdminSession.id != except_session_id)
    return getattr(db.execute(stmt), "rowcount", 0) or 0


def logout(db: Session, user: AdminUser, session: AdminSession, request: Request) -> None:
    _revoke(session, "logout")
    audit.record(db, action="auth.logout", actor=user, resource_type="admin_user", resource_id=user.id, request=request)
    db.commit()


def change_password(db: Session, user: AdminUser, session: AdminSession, current: str, new: str,
                    request: Request) -> None:
    if not verify_password(current, user.password_hash):
        audit.record_now(action="auth.password_change_failed", outcome="failure", actor=user,
                         resource_type="admin_user", resource_id=user.id, request=request)
        raise AppError("Your current password is incorrect.", code="invalid_password",
                       details=[{"field": "current_password", "message": "Incorrect password"}])
    _check_new_password(user, new, "new_password")
    if verify_password(new, user.password_hash):
        raise AppError("Choose a password different from the current one.", code="password_reused",
                       details=[{"field": "new_password", "message": "Same as current password"}])
    user.password_hash = hash_password(new)
    revoked = revoke_all(db, user.id, "password_changed", except_session_id=session.id)
    audit.record(db, action="auth.password_changed", actor=user, resource_type="admin_user", resource_id=user.id,
                 details={"other_sessions_revoked": revoked}, request=request)
    db.commit()


# -- Password reset ----------------------------------------------------------

def request_password_reset(db: Session, email: str, request: Request, background: BackgroundTasks) -> None:
    """Always behaves the same whether or not the email exists."""
    s = get_settings()
    email = email.strip().lower()
    user = db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none()
    if user is None or not user.is_active:
        audit.record_now(action="auth.password_reset_requested", outcome="failure", actor_type="anonymous",
                         actor_email=email, details={"reason": "no_active_account"}, request=request)
        return
    now = utcnow()
    # Only the newest link works
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=now).execution_options(synchronize_session=False))
    token = new_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=sha256_hex(token), created_at=now,
                              expires_at=now + timedelta(minutes=s.password_reset_minutes),
                              requested_ip=client_ip(request)))
    audit.record(db, action="auth.password_reset_requested", actor_type="anonymous", actor_email=email,
                 resource_type="admin_user", resource_id=user.id, request=request)
    db.commit()
    link = f"{s.public_base_url.rstrip('/')}/admin/reset-password#token={token}"
    background.add_task(
        send_mail, user.email, "Reset your Tycoons admin password",
        f"Hello {user.full_name},\n\nUse this link within {s.password_reset_minutes} minutes to choose a new "
        f"password:\n\n{link}\n\nIf you did not ask for this, ignore this email; your password is unchanged.\n",
    )


def reset_password(db: Session, token: str, new: str, request: Request) -> None:
    row = db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == sha256_hex(token))
                     .with_for_update()).scalar_one_or_none() if token and len(token) <= 100 else None
    now = utcnow()
    if row is None or row.used_at is not None or row.expires_at <= now:
        db.rollback()
        audit.record_now(action="auth.password_reset_failed", outcome="failure", actor_type="anonymous",
                         details={"reason": "invalid_or_expired_token"}, request=request)
        raise AppError("This reset link is invalid or has expired. Request a new one.", code="invalid_reset_token")
    user = db.get(AdminUser, row.user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise AppError("This reset link is invalid or has expired. Request a new one.", code="invalid_reset_token")
    _check_new_password(user, new, "new_password")
    user.password_hash = hash_password(new)
    row.used_at = now
    revoke_all(db, user.id, "password_reset")
    audit.record(db, action="auth.password_reset", actor_type="anonymous", actor_email=user.email,
                 resource_type="admin_user", resource_id=user.id, request=request)
    db.commit()
