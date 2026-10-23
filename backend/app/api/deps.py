from __future__ import annotations

import hmac

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.security import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, decode_session_token
from app.db.session import get_db
from app.models import AdminUser
from app.models.enums import AdminRole

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_session_token(token) if token else None
    if payload is None:
        raise Unauthorized("Please sign in.", code="not_authenticated")
    try:
        user = db.get(AdminUser, int(payload["sub"]))
    except (TypeError, ValueError):
        user = None
    if user is None or not user.is_active or user.token_version != payload.get("ver"):
        raise Unauthorized("Your session has ended. Please sign in again.", code="session_expired")

    # Double-submit CSRF check for every state-changing admin request
    if request.method not in SAFE_METHODS:
        cookie = request.cookies.get(CSRF_COOKIE, "")
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not hmac.compare_digest(cookie, header):
            raise Forbidden("Security check failed. Refresh the page and try again.", code="csrf_failed")
    return user


def require_admin(user: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if user.role != AdminRole.ADMIN:
        raise Forbidden("Only administrators can do this.", code="admin_only")
    return user
