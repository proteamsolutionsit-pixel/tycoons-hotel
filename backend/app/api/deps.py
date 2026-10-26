"""Authentication and authorisation dependencies for the admin API.

    @router.post(..., dependencies=[...])
    def handler(user: AdminUser = Depends(require(Permission.PAYMENTS_REFUND))): ...

`require(permission)` authenticates the session cookie, enforces CSRF on
state-changing methods and checks the permission. Every admin route must use
it (tests/test_permissions.py enumerates the routes to make sure).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import Permission, user_can
from app.core.security import CSRF_HEADER, SESSION_COOKIE, constant_time_equals, sha256_hex
from app.db.session import get_db
from app.models import AdminSession, AdminUser
from app.services import audit, auth_service

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class Principal:
    user: AdminUser
    session: AdminSession


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    resolved = auth_service.authenticate(db, request.cookies.get(SESSION_COOKIE, ""))
    if resolved is None:
        raise Unauthorized("Please sign in.", code="not_authenticated")
    user, session = resolved
    if request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER, "")
        if not header or not constant_time_equals(sha256_hex(header), session.csrf_hash):
            audit.record_now(action="security.csrf_rejected", outcome="denied", actor=user,
                             details={"path": request.url.path, "method": request.method}, request=request)
            raise Forbidden("Security check failed. Refresh the page and try again.", code="csrf_failed")
    request.state.admin_id = user.id
    return Principal(user=user, session=session)


def get_current_admin(principal: Principal = Depends(get_principal)) -> AdminUser:
    return principal.user


class _Require:
    def __init__(self, permission: Permission):
        self.permission = permission

    def __call__(self, request: Request, principal: Principal = Depends(get_principal)) -> AdminUser:
        user = principal.user
        if not user_can(user, self.permission):
            audit.record_now(action="security.permission_denied", outcome="denied", actor=user,
                             details={"permission": self.permission.value, "path": request.url.path,
                                      "method": request.method}, request=request)
            raise Forbidden("You don't have permission to do this.", code="permission_denied")
        return user


def require(permission: Permission) -> _Require:
    return _Require(permission)
