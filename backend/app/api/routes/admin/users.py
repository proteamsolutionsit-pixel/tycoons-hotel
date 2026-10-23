"""Staff accounts (administrators only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.errors import AppError, Conflict, NotFound
from app.core.security import hash_password, password_problems
from app.db.session import get_db
from app.models import AdminUser
from app.models.enums import AdminRole
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordReset
from app.schemas.common import Message

router = APIRouter(prefix="/users", tags=["Admin: users"])


def _check_password(pw: str) -> None:
    if problems := password_problems(pw):
        raise AppError("Password needs " + ", ".join(problems) + ".", code="weak_password",
                       details=[{"field": "password", "message": "Needs " + ", ".join(problems)}])


def _active_admins(db: Session) -> int:
    return db.execute(select(func.count()).select_from(AdminUser).where(
        AdminUser.role == AdminRole.ADMIN, AdminUser.is_active.is_(True))).scalar_one()


@router.get("", response_model=list[AdminUserOut])
def list_users(_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    return db.execute(select(AdminUser).order_by(AdminUser.id)).scalars().all()


@router.post("", response_model=AdminUserOut, status_code=201)
def create_user(data: AdminUserCreate, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    _check_password(data.password)
    email = str(data.email).lower()
    if db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none():
        raise Conflict("A user with that email already exists.", code="duplicate_email")
    user = AdminUser(email=email, full_name=data.full_name.strip(), role=data.role,
                     password_hash=hash_password(data.password), is_active=True)
    db.add(user)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: AdminUserUpdate, me: AdminUser = Depends(require_admin),
                db: Session = Depends(get_db)):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    demoting = (data.role is not None and data.role != AdminRole.ADMIN) or data.is_active is False
    if demoting and user.role == AdminRole.ADMIN and user.is_active and _active_admins(db) <= 1:
        raise Conflict("You can't remove the last active administrator.", code="last_admin")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    if "role" in changes or changes.get("is_active") is False:
        user.token_version += 1  # re-evaluate permissions: force a fresh sign-in
    db.commit()
    return user


@router.post("/{user_id}/reset-password", response_model=Message)
def reset_password(user_id: int, data: PasswordReset, _: AdminUser = Depends(require_admin),
                   db: Session = Depends(get_db)):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise NotFound("User not found.")
    _check_password(data.new_password)
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    return Message(message="Password reset. The user's existing sessions were signed out.")
