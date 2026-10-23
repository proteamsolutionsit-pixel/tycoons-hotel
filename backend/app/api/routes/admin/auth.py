"""Staff sign-in. The session is an HttpOnly cookie carrying a signed JWT;
a second, readable cookie carries the CSRF token the SPA echoes back in the
X-CSRF-Token header on every state-changing request."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.errors import AppError, Unauthorized
from app.core.rate_limit import enforce
from app.core.security import (CSRF_COOKIE, DUMMY_HASH, SESSION_COOKIE, create_session_token, hash_password,
                               new_csrf_token, password_problems, verify_password)
from app.core.timeutil import utcnow
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.admin import AdminUserOut, LoginIn, PasswordChange
from app.schemas.common import Message

log = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["Admin: auth"])


def _set_session(response: Response, user: AdminUser) -> None:
    s = get_settings()
    max_age = s.jwt_expire_minutes * 60
    response.set_cookie(SESSION_COOKIE, create_session_token(user.id, user.token_version), max_age=max_age,
                        httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite, path="/api")
    response.set_cookie(CSRF_COOKIE, new_csrf_token(), max_age=max_age, httponly=False,
                        secure=s.cookie_secure, samesite=s.cookie_samesite, path="/")


def _clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/login", response_model=AdminUserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    enforce(request, "admin-login", 10, 600)                 # per IP
    enforce(request, "admin-login-user", 5, 600, extra_key=email)  # per IP + account
    user = db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none()
    ok = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        log.warning("Admin login failed", extra={"email": email})
        raise Unauthorized("Incorrect email or password.", code="invalid_credentials")
    user.last_login_at = utcnow()
    db.commit()
    _set_session(response, user)
    log.info("Admin login", extra={"admin_id": user.id})
    return user


@router.post("/logout", response_model=Message)
def logout(response: Response, user: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    user.token_version += 1  # invalidates this and any other outstanding session token
    db.commit()
    _clear_session(response)
    return Message(message="Signed out")


@router.get("/me", response_model=AdminUserOut)
def me(user: AdminUser = Depends(get_current_admin)):
    return user


@router.post("/change-password", response_model=Message)
def change_password(data: PasswordChange, request: Request, response: Response,
                    user: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    enforce(request, "admin-password", 5, 600, extra_key=str(user.id))
    if not verify_password(data.current_password, user.password_hash):
        raise AppError("Your current password is incorrect.", code="invalid_password",
                       details=[{"field": "current_password", "message": "Incorrect password"}])
    if problems := password_problems(data.new_password):
        raise AppError("New password needs " + ", ".join(problems) + ".", code="weak_password",
                       details=[{"field": "new_password", "message": "Needs " + ", ".join(problems)}])
    if verify_password(data.new_password, user.password_hash):
        raise AppError("Choose a password different from the current one.", code="password_reused",
                       details=[{"field": "new_password", "message": "Same as current password"}])
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    _set_session(response, user)  # keep this browser signed in; others are signed out
    return Message(message="Password changed")
