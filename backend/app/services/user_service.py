"""Staff account administration."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.core.security import hash_password, password_problems
from app.models import AdminUser
from app.models.enums import AdminRole
from app.schemas.admin import AdminUserCreate, AdminUserUpdate
from app.services import audit
from app.services.auth_service import revoke_all


def _active_admins(db: Session) -> int:
    return db.execute(select(func.count()).select_from(AdminUser).where(
        AdminUser.role == AdminRole.ADMIN, AdminUser.is_active.is_(True))).scalar_one()


def _check(pw: str, email: str, name: str) -> None:
    if problems := password_problems(pw, email=email, name=name):
        raise AppError("Password needs " + ", ".join(problems) + ".", code="weak_password",
                       details=[{"field": "password", "message": "Needs " + ", ".join(problems)}])


def create(db: Session, data: AdminUserCreate, actor: AdminUser, request: Request) -> AdminUser:
    email = str(data.email).lower()
    _check(data.password, email, data.full_name)
    if db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none():
        raise Conflict("A user with that email already exists.", code="duplicate_email")
    user = AdminUser(email=email, full_name=data.full_name.strip(), role=data.role,
                     password_hash=hash_password(data.password), is_active=True)
    db.add(user)
    db.flush()
    audit.record(db, action="user.create", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"email": email, "role": data.role.value}, request=request)
    db.commit()
    return user


def update(db: Session, user_id: int, data: AdminUserUpdate, actor: AdminUser, request: Request) -> AdminUser:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    changes = data.model_dump(exclude_unset=True)
    demoting = (changes.get("role") not in (None, AdminRole.ADMIN)) or changes.get("is_active") is False
    if demoting and user.role == AdminRole.ADMIN and user.is_active and _active_admins(db) <= 1:
        raise Conflict("You can't remove the last active administrator.", code="last_admin")
    before = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    if ("role" in changes and before["role"] != user.role) or changes.get("is_active") is False:
        revoke_all(db, user.id, "access_changed")  # rights changed: sign in again
    audit.record(db, action="user.update", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"changes": {k: {"from": getattr(before[k], "value", before[k]),
                                          "to": getattr(getattr(user, k), "value", getattr(user, k))}
                                      for k in changes}},
                 request=request)
    db.commit()
    return user


def reset_password(db: Session, user_id: int, new_password: str, actor: AdminUser, request: Request) -> None:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    _check(new_password, user.email, user.full_name)
    user.password_hash = hash_password(new_password)
    revoked = revoke_all(db, user.id, "password_reset_by_admin")
    audit.record(db, action="user.password_reset", actor=actor, resource_type="admin_user", resource_id=user.id,
                 details={"sessions_revoked": revoked}, request=request)
    db.commit()
