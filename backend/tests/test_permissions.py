"""Authorisation matrix, generated from the live route table: every admin
endpoint must declare a permission, refuse anonymous callers, and refuse
staff where the staff role lacks that permission."""
import re

import pytest
from fastapi.routing import iter_route_contexts

from app.api.deps import _Require
from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.main import app
from app.models.enums import AdminRole
from tests.conftest import STAFF_PW, login

# Admin routes that are deliberately reachable without a permission check
PUBLIC_ADMIN = {"/api/v1/admin/auth/login", "/api/v1/admin/auth/password-reset/request",
                "/api/v1/admin/auth/password-reset/confirm"}
# Session-only (any signed-in staff member, about themselves)
SESSION_ONLY = {"/api/v1/admin/auth/logout", "/api/v1/admin/auth/me", "/api/v1/admin/auth/change-password"}


def _permission(dependant):
    for d in dependant.dependencies:
        if isinstance(d.call, _Require):
            return d.call.permission
        found = _permission(d)
        if found:
            return found
    return None


def _admin_routes():
    out = []
    for ctx in iter_route_contexts(app.routes):
        path = getattr(ctx, "path", "")
        if not path.startswith("/api/v1/admin"):
            continue
        for method in sorted(ctx.methods or []):
            out.append((method, path, _permission(ctx.route.dependant)))
    return out


ROUTES = _admin_routes()


def _concrete(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: "applications" if m.group(1) == "kind" else "1", path)


def test_route_table_is_populated():
    assert len(ROUTES) > 40


@pytest.mark.parametrize("method,path,perm", ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_every_admin_route_declares_a_permission(method, path, perm):
    if path in PUBLIC_ADMIN | SESSION_ONLY:
        return
    assert perm is not None, f"{method} {path} has no require(Permission...) dependency"


@pytest.mark.parametrize("method,path,perm", ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_anonymous_is_refused(client, method, path, perm):
    if path in PUBLIC_ADMIN:
        return
    r = client.request(method, _concrete(path), json={})
    assert r.status_code == 401, (method, path, r.status_code)


STAFF_DENIED = [(m, p, perm) for m, p, perm in ROUTES
                if perm is not None and perm not in ROLE_PERMISSIONS[AdminRole.STAFF]]


@pytest.mark.parametrize("method,path,perm", STAFF_DENIED, ids=[f"{m} {p}" for m, p, _ in STAFF_DENIED])
def test_staff_is_refused_outside_their_permissions(client, method, path, perm):
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    r = client.request(method, _concrete(path), json={}, headers=headers)
    assert r.status_code == 403, (method, path, r.status_code, r.text)
    assert r.json()["error"]["code"] == "permission_denied"


def test_staff_can_do_front_desk_work(client):
    login(client, "staff@tycoons.example.com", STAFF_PW)
    for path in ("/api/v1/admin/dashboard", "/api/v1/admin/bookings", "/api/v1/admin/payments",
                 "/api/v1/admin/submissions/enquiries", "/api/v1/admin/room-types", "/api/v1/admin/occupancy"):
        assert client.get(path).status_code == 200, path
    me = client.get("/api/v1/admin/auth/me").json()
    assert "payments.refund" not in me["permissions"] and "bookings.view" in me["permissions"]


def test_admin_role_has_every_permission():
    assert ROLE_PERMISSIONS[AdminRole.ADMIN] == frozenset(Permission)


def test_permission_denials_are_audited(client, db):
    from app.models import AuditLog
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    client.patch("/api/v1/admin/room-types/1", json={"base_rate_paise": 100}, headers=headers)
    row = db.query(AuditLog).filter_by(action="security.permission_denied").one()
    assert row.outcome == "denied" and row.details["permission"] == "catalog.manage"


def test_unknown_fields_are_rejected_on_admin_writes(client, admin_headers):
    r = client.patch("/api/v1/admin/room-types/1", json={"base_rate_paise": 700000, "id": 99, "created_at": "x"},
                     headers=admin_headers)
    assert r.status_code == 422
    r = client.patch("/api/v1/admin/users/1", json={"password_hash": "x"}, headers=admin_headers)
    assert r.status_code == 422
