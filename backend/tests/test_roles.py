"""Roles & access: administrators define roles, assign them to users, and the
API enforces exactly the ticked permissions - with no way to escalate."""
from app.models import AdminUser, AuditLog, Role
from tests.conftest import STAFF_PW, login

R = "/api/v1/admin/roles"
U = "/api/v1/admin/users"
PW = "Quiet-Harbour-482"  # pragma: allowlist secret


def _role(client, headers, name, permissions):
    r = client.post(R, json={"name": name, "description": "test", "permissions": permissions}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _user(client, headers, email, role_id):
    r = client.post(U, json={"email": email, "full_name": "Role Tester", "role_id": role_id, "password": PW},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_built_in_roles_exist_and_users_have_them(client, admin_headers):
    roles = {r["key"]: r for r in client.get(R).json()}
    assert roles["administrator"]["is_system"] and roles["administrator"]["user_count"] == 1
    assert "roles.manage" not in roles["front_desk"]["permissions"] and roles["front_desk"]["user_count"] == 1
    me = client.get("/api/v1/admin/auth/me").json()
    assert me["role_name"] == "Administrator" and "roles.manage" in me["permissions"]


def test_catalogue_lists_grantable_permissions_only(client, admin_headers):
    keys = [p["key"] for p in client.get(R + "/permissions").json()]
    assert "bookings.view" in keys and "roles.manage" not in keys


def test_custom_role_grants_exactly_its_permissions(client, admin_headers):
    role = _role(client, admin_headers, "Night auditor", ["payments.reconcile", "audit.view"])
    # implied permissions are added; unknown and non-grantable ones are dropped
    assert set(role["permissions"]) == {"payments.reconcile", "payments.view", "bookings.view", "audit.view"}
    _user(client, admin_headers, "night@tycoons.example.com", role["id"])
    client.cookies.clear()
    login(client, "night@tycoons.example.com", PW)
    assert client.get("/api/v1/admin/audit-logs").status_code == 200
    assert client.get("/api/v1/admin/payments").status_code == 200
    assert client.get("/api/v1/admin/dashboard").status_code == 403            # not ticked
    assert client.get("/api/v1/admin/submissions/enquiries").status_code == 403
    me = client.get("/api/v1/admin/auth/me").json()
    assert me["role_name"] == "Night auditor" and "dashboard.view" not in me["permissions"]


def test_role_changes_apply_on_the_next_request(client, admin_headers, db):
    role = _role(client, admin_headers, "Reception", ["dashboard.view"])
    _user(client, admin_headers, "rec@tycoons.example.com", role["id"])
    staff_client_headers = None
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as other:
        staff_client_headers = login(other, "rec@tycoons.example.com", PW)
        assert other.get("/api/v1/admin/bookings").status_code == 403
        r = client.patch(f"{R}/{role['id']}", json={"permissions": ["dashboard.view", "bookings.view"]}, headers=admin_headers)
        assert r.status_code == 200
        assert other.get("/api/v1/admin/bookings").status_code == 200        # same session, new rights
    assert staff_client_headers
    entry = db.query(AuditLog).filter_by(action="role.update").one()
    assert entry.details["permissions_added"] == ["bookings.view"] and entry.details["permissions_removed"] == []


def test_administrator_role_is_locked(client, admin_headers):
    admin = next(r for r in client.get(R).json() if r["is_system"])
    assert client.patch(f"{R}/{admin['id']}", json={"permissions": []}, headers=admin_headers).status_code == 409
    assert client.delete(f"{R}/{admin['id']}", headers=admin_headers).status_code == 409


def test_role_in_use_cannot_be_deleted_and_names_are_unique(client, admin_headers, db):
    role = _role(client, admin_headers, "Spa desk", ["submissions.manage"])
    assert client.post(R, json={"name": "spa DESK", "permissions": []}, headers=admin_headers).status_code == 409
    user = _user(client, admin_headers, "spa@tycoons.example.com", role["id"])
    assert client.delete(f"{R}/{role['id']}", headers=admin_headers).status_code == 409
    front = next(r for r in client.get(R).json() if r["key"] == "front_desk")
    assert client.patch(f"{U}/{user['id']}", json={"role_id": front["id"]}, headers=admin_headers).status_code == 200
    assert client.delete(f"{R}/{role['id']}", headers=admin_headers).status_code == 204
    assert db.get(Role, role["id"]) is None


def test_only_administrators_manage_roles(client):
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.post(R, json={"name": "Sneaky", "permissions": ["users.manage"]}, headers=headers).status_code == 403


def test_user_managers_cannot_escalate(client, admin_headers, db):
    # A role that can manage users but not refunds or the payment gateway
    hr = _role(client, admin_headers, "HR", ["users.manage", "dashboard.view"])
    rich = _role(client, admin_headers, "Finance", ["payments.refund"])
    _user(client, admin_headers, "hr@tycoons.example.com", hr["id"])
    admin_id = db.query(AdminUser).filter_by(email="admin@tycoons.example.com").one().id
    administrator = next(r for r in client.get(R).json() if r["is_system"])
    client.cookies.clear()
    headers = login(client, "hr@tycoons.example.com", PW)
    me_id = client.get("/api/v1/admin/auth/me").json()["id"]
    # can't hand out more than they have - to others or themselves
    r = client.post(U, json={"email": "x@tycoons.example.com", "full_name": "X Y", "role_id": rich["id"], "password": PW}, headers=headers)
    assert r.status_code == 403
    assert client.patch(f"{U}/{me_id}", json={"role_id": administrator["id"]}, headers=headers).status_code == 403
    # can't touch someone with more access (e.g. take over the administrator)
    assert client.post(f"{U}/{admin_id}/reset-password", json={"new_password": PW}, headers=headers).status_code == 403
    assert client.patch(f"{U}/{admin_id}", json={"is_active": False}, headers=headers).status_code == 403
    # but can create users within their own access
    assert client.post(U, json={"email": "y@tycoons.example.com", "full_name": "Y Z", "role_id": hr["id"], "password": PW},
                       headers=headers).status_code == 201


def test_last_administrator_is_protected(client, admin_headers, db):
    admin = db.query(AdminUser).filter_by(email="admin@tycoons.example.com").one()
    front = next(r for r in client.get(R).json() if r["key"] == "front_desk")
    r = client.patch(f"{U}/{admin.id}", json={"role_id": front["id"]}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"


def test_legacy_role_field_still_works(client, admin_headers):
    r = client.post(U, json={"email": "legacy@tycoons.example.com", "full_name": "Legacy User", "role": "staff",
                             "password": PW}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["role_name"] == "Front desk" and r.json()["role"] == "staff"


def test_admin_can_change_a_users_sign_in_email(client, admin_headers, db):
    admin = db.query(AdminUser).filter_by(email="admin@tycoons.example.com").one()
    r = client.patch(f"{U}/{admin.id}", json={"email": "Boss@Tycoons.Example.com"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["email"] == "boss@tycoons.example.com"
    entry = db.query(AuditLog).filter_by(action="user.update").one()
    assert entry.details["changes"]["email"] == {"from": "admin@tycoons.example.com", "to": "boss@tycoons.example.com"}
    # duplicates refused; the new address signs in
    staff = db.query(AdminUser).filter_by(email="staff@tycoons.example.com").one()
    assert client.patch(f"{U}/{staff.id}", json={"email": "boss@tycoons.example.com"}, headers=admin_headers).status_code == 409
    client.cookies.clear()
    from tests.conftest import ADMIN_PW
    login(client, "boss@tycoons.example.com", ADMIN_PW)
    assert client.get("/api/v1/admin/auth/me").json()["email"] == "boss@tycoons.example.com"


def test_user_manager_cannot_change_an_administrators_email(client, admin_headers, db):
    hr = _role(client, admin_headers, "HR desk", ["users.manage"])
    _user(client, admin_headers, "hr2@tycoons.example.com", hr["id"])
    admin_id = db.query(AdminUser).filter_by(email="admin@tycoons.example.com").one().id
    client.cookies.clear()
    headers = login(client, "hr2@tycoons.example.com", PW)
    assert client.patch(f"{U}/{admin_id}", json={"email": "evil@tycoons.example.com"}, headers=headers).status_code == 403
