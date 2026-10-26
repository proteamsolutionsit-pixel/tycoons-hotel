"""Staff account administration."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.permissions import user_permissions
from app.core.security import hash_password, password_problems
from app.models import AdminUser, Role
from app.models.enums import AdminRole
from app.models.role import ADMINISTRATOR_KEY, FRONT_DESK_KEY
from app.schemas.admin import AdminUserCreate, AdminUserUpdate
from app.services import audit, role_service
from app.services.auth_service import revoke_all


def _active_admins(db: Session) -> int:
    return db.execute(select(func.count()).select_from(AdminUser).where(
        AdminUser.role == AdminRole.ADMIN, AdminUser.is_active.is_(True))).scalar_one()


def _resolve_role(db: Session, role_id: int | None, legacy: AdminRole | None) -> Role | None:
    if role_id is not None:
        return role_service.get(db, role_id)
    if legacy is not None:
        return role_service.by_key(db, ADMINISTRATOR_KEY if legacy == AdminRole.ADMIN else FRONT_DESK_KEY)
    return None


def _assign(user: AdminUser, role: Role) -> None:
    user.role_id = role.id
    user.access_role = role
    user.role = AdminRole.ADMIN if role.is_system else AdminRole.STAFF   # keep the legacy flag in step


def _guard_target(actor: AdminUser, user: AdminUser) -> None:
    """Managing staff never reaches above your own access (e.g. resetting an administrator's password)."""
    if actor.id != user.id and user_permissions(user) - user_permissions(actor):
        raise Forbidden("You can't change a user who has more access than you.", code="target_exceeds_own_access")


def _check(pw: str, email: str, name: str) -> None:
    if problems := password_problems(pw, email=email, name=name):
        raise AppError("Password needs " + ", ".join(problems) + ".", code="weak_password",
                       details=[{"field": "password", "message": "Needs " + ", ".join(problems)}])


def create(db: Session, data: AdminUserCreate, actor: AdminUser, request: Request) -> AdminUser:
    email = str(data.email).lower()
    _check(data.password, email, data.full_name)
    if db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none():
        raise Conflict("A user with that email already exists.", code="duplicate_email")
    role = _resolve_role(db, data.role_id, data.role) or role_service.by_key(db, FRONT_DESK_KEY)
    role_service.check_can_assign(actor, role)
    user = AdminUser(email=email, full_name=data.full_name.strip(), password_hash=hash_password(data.password),
                     is_active=True)
    _assign(user, role)
    db.add(user)
    db.flush()
    audit.record(db, action="user.create", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"email": email, "role": role.name}, request=request)
    db.commit()
    return user


def update(db: Session, user_id: int, data: AdminUserUpdate, actor: AdminUser, request: Request) -> AdminUser:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    _guard_target(actor, user)
    changes = data.model_dump(exclude_unset=True)
    new_role = _resolve_role(db, changes.pop("role_id", None), changes.pop("role", None))
    if new_role is not None:
        role_service.check_can_assign(actor, new_role)
    demoting = (new_role is not None and not new_role.is_system) or changes.get("is_active") is False
    if demoting and user.role == AdminRole.ADMIN and user.is_active and _active_admins(db) <= 1:
        raise Conflict("You can't remove the last active administrator.", code="last_admin")
    diff: dict = {}
    if new_role is not None and new_role.id != user.role_id:
        diff["role"] = {"from": user.role_name, "to": new_role.name}
        _assign(user, new_role)
    for k, v in changes.items():
        v = v.strip() if isinstance(v, str) else v
        if getattr(user, k) != v:
            diff[k] = {"from": getattr(user, k), "to": v}
            setattr(user, k, v)
    if "role" in diff or changes.get("is_active") is False:
        revoke_all(db, user.id, "access_changed")  # rights changed: sign in again
    audit.record(db, action="user.update", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"changes": diff}, request=request)
    db.commit()
    return user


def reset_password(db: Session, user_id: int, new_password: str, actor: AdminUser, request: Request) -> None:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    _guard_target(actor, user)
    _check(new_password, user.email, user.full_name)
    user.password_hash = hash_password(new_password)
    revoked = revoke_all(db, user.id, "password_reset_by_admin")
    audit.record(db, action="user.password_reset", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"sessions_revoked": revoked}, request=request)
    db.commit()
