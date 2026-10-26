"""Access roles: the built-in ones, and the roles administrators define.

Rules:
* Administrator (is_system) has every permission; it cannot be edited or deleted.
* Permissions are normalised: unknown or non-grantable values are dropped and
  implied ones added (e.g. "manage bookings" brings "view bookings").
* A role that users still hold cannot be deleted.
* A user who manages staff can assign only roles within their own access.
"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.permissions import ROLE_PERMISSIONS, Permission, normalise, user_permissions
from app.models import AdminUser, Role
from app.models.enums import AdminRole
from app.models.role import ADMINISTRATOR_KEY, FRONT_DESK_KEY
from app.services import audit

BUILT_IN: tuple[tuple[str, str, str, bool, list[str]], ...] = (
    (ADMINISTRATOR_KEY, "Administrator", "Full access to everything, including roles and payment keys.", True, []),
    (FRONT_DESK_KEY, "Front desk", "Bookings and payments (read), guest requests, rooms and content (read).", False,
     sorted(p.value for p in ROLE_PERMISSIONS[AdminRole.STAFF])),
)


def ensure_built_in(db: Session) -> None:
    """Create the built-in roles if missing (seed; idempotent)."""
    for key, name, description, is_system, perms in BUILT_IN:
        if db.execute(select(Role).where(Role.key == key)).scalar_one_or_none() is None:
            db.add(Role(key=key, name=name, description=description, is_system=is_system, permissions=normalise(perms)))
    db.flush()


def by_key(db: Session, key: str) -> Role:
    role = db.execute(select(Role).where(Role.key == key)).scalar_one_or_none()
    if role is None:
        ensure_built_in(db)
        role = db.execute(select(Role).where(Role.key == key)).scalar_one()
    return role


def get(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("Role not found.")
    return role


def user_counts(db: Session) -> dict[int, int]:
    rows = db.execute(select(AdminUser.role_id, func.count()).where(AdminUser.role_id.is_not(None))
                      .group_by(AdminUser.role_id)).all()
    return {rid: n for rid, n in rows}


def role_permissions(role: Role) -> frozenset[Permission]:
    return frozenset(Permission) if role.is_system else frozenset(Permission(v) for v in normalise(role.permissions))


def check_can_assign(actor: AdminUser, role: Role) -> None:
    """No privilege escalation: hand out only access you hold yourself."""
    missing = role_permissions(role) - user_permissions(actor)
    if missing:
        raise Forbidden("You can't assign a role with more access than your own.", code="role_exceeds_own_access")


def _validate_name(db: Session, name: str, exclude_id: int | None = None) -> str:
    name = " ".join(name.split())
    if len(name) < 2:
        raise AppError("Enter a role name.", code="validation_error", status_code=422,
                       details=[{"field": "name", "message": "Enter a role name."}])
    clash = db.execute(select(Role).where(func.lower(Role.name) == name.lower())).scalar_one_or_none()
    if clash is not None and clash.id != exclude_id:
        raise Conflict("Another role already has that name.", code="duplicate",
                       details=[{"field": "name", "message": "Another role already has that name."}])
    return name


def create(db: Session, *, name: str, description: str | None, permissions: list[str], actor: AdminUser,
           request: Request) -> Role:
    role = Role(name=_validate_name(db, name), description=(description or "").strip() or None,
                permissions=normalise(permissions), is_system=False)
    db.add(role)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Another role already has that name.", code="duplicate") from exc
    audit.record(db, action="role.create", actor=actor, resource_type="role", resource_id=role.id,
                 details={"name": role.name, "permissions": role.permissions}, request=request)
    db.commit()
    db.refresh(role)
    return role


def update(db: Session, role_id: int, *, changes: dict, actor: AdminUser, request: Request) -> Role:
    role = get(db, role_id)
    if role.is_system:
        raise Conflict("The Administrator role always has full access and can't be changed.", code="system_role")
    before_name, before_description = role.name, role.description
    before_permissions: list[str] = list(role.permissions or [])
    if changes.get("name") is not None:
        role.name = _validate_name(db, changes["name"], exclude_id=role.id)
    if "description" in changes:
        role.description = (changes["description"] or "").strip() or None
    if changes.get("permissions") is not None:
        role.permissions = normalise(changes["permissions"])
    diff: dict = {}
    if role.name != before_name:
        diff["name"] = {"from": before_name, "to": role.name}
    if role.description != before_description:
        diff["description"] = {"from": before_description, "to": role.description}
    added = sorted(set(role.permissions) - set(before_permissions))
    removed = sorted(set(before_permissions) - set(role.permissions))
    if diff or added or removed:
        # kept shallow: the audit log trims details nested deeper than three levels
        audit.record(db, action="role.update", actor=actor, resource_type="role", resource_id=role.id,
                     details={"name": role.name, "changes": diff, "permissions_added": added,
                              "permissions_removed": removed}, request=request)
    db.commit()
    db.refresh(role)
    return role


def delete(db: Session, role_id: int, *, actor: AdminUser, request: Request) -> None:
    role = get(db, role_id)
    if role.is_system or role.key == FRONT_DESK_KEY:
        raise Conflict("Built-in roles can't be deleted.", code="system_role")
    in_use = db.execute(select(func.count()).select_from(AdminUser).where(AdminUser.role_id == role.id)).scalar_one()
    if in_use:
        raise Conflict(f"{in_use} user(s) still have this role. Give them another role first.", code="in_use")
    audit.record(db, action="role.delete", actor=actor, resource_type="role", resource_id=role.id,
                 details={"name": role.name, "permissions": role.permissions}, request=request)
    db.delete(role)
    db.commit()
