"""Staff sign-in, sessions and passwords.

Cookies: `tyc_admin` (HttpOnly, opaque session token, path /api) and
`tyc_csrf` (readable by the SPA, echoed in X-CSRF-Token; its hash is bound
to the session server-side)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal
from app.core.config import get_settings
from app.core.permissions import permissions_for
from app.core.rate_limit import enforce
from app.core.security import CSRF_COOKIE, SESSION_COOKIE
from app.db.session import get_db
from app.schemas.admin import LoginIn, MeOut, PasswordChange
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Admin: auth"])


def _set_cookies(response: Response, issued: auth_service.IssuedSession) -> None:
    s = get_settings()
    max_age = s.session_absolute_hours * 3600  # the server enforces idle expiry separately
    response.set_cookie(SESSION_COOKIE, issued.token, max_age=max_age, httponly=True, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/api")
    response.set_cookie(CSRF_COOKIE, issued.csrf, max_age=max_age, httponly=False, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _me(user) -> MeOut:
    return MeOut.model_validate(user).model_copy(
        update={"permissions": sorted(p.value for p in permissions_for(user.role))})


@router.post("/login", response_model=MeOut, summary="Sign in (rate limited per IP and per account)")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    enforce(request, "admin-login", 10, 600)
    enforce(request, "admin-login-account", 5, 600, extra_key=email)                 # per IP + account
    enforce(request, "admin-login-account-global", 20, 3600, extra_key=email, per_ip=False)  # distributed guessing
    issued = auth_service.login(db, email, data.password, request)
    _set_cookies(response, issued)
    return _me(issued.user)


@router.post("/logout", response_model=Message)
def logout(request: Request, response: Response, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    auth_service.logout(db, p.user, p.session, request)
    _clear_cookies(response)
    return Message(message="Signed out")


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal)):
    return _me(p.user)


@router.post("/change-password", response_model=Message)
def change_password(data: PasswordChange, request: Request, p: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)):
    enforce(request, "admin-password", 5, 600, extra_key=str(p.user.id))
    auth_service.change_password(db, p.user, p.session, data.current_password, data.new_password, request)
    return Message(message="Password changed. Your other sessions were signed out.")


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    new_password: str = Field(min_length=12, max_length=128)


@router.post("/password-reset/request", response_model=Message, status_code=202,
             summary="Email a password-reset link (same reply whether or not the account exists)")
def request_reset(data: ResetRequestIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    enforce(request, "admin-reset-request", 5, 3600)
    enforce(request, "admin-reset-request-account", 3, 3600, extra_key=str(data.email).lower(), per_ip=False)
    auth_service.request_password_reset(db, str(data.email), request, background)
    return Message(message="If that address belongs to a staff account, a reset link is on its way.")


@router.post("/password-reset/confirm", response_model=Message, summary="Set a new password with a reset token")
def confirm_reset(data: ResetIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "admin-reset-confirm", 10, 3600)
    auth_service.reset_password(db, data.token, data.new_password, request)
    return Message(message="Password updated. You can now sign in.")
