"""Staff accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordReset
from app.schemas.common import Message
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Admin: users"])
MANAGE = require(Permission.USERS_MANAGE)


@router.get("", response_model=list[AdminUserOut])
def list_users(_: AdminUser = Depends(MANAGE), db: Session = Depends(get_db)):
    return db.execute(select(AdminUser).order_by(AdminUser.id)).scalars().all()


@router.post("", response_model=AdminUserOut, status_code=201)
def create_user(data: AdminUserCreate, request: Request, actor: AdminUser = Depends(MANAGE),
                db: Session = Depends(get_db)):
    return user_service.create(db, data, actor, request)


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: AdminUserUpdate, request: Request, actor: AdminUser = Depends(MANAGE),
                db: Session = Depends(get_db)):
    return user_service.update(db, user_id, data, actor, request)


@router.post("/{user_id}/reset-password", response_model=Message)
def reset_password(user_id: int, data: PasswordReset, request: Request, actor: AdminUser = Depends(MANAGE),
                   db: Session = Depends(get_db)):
    user_service.reset_password(db, user_id, data.new_password, actor, request)
    return Message(message="Password reset. The user's existing sessions were signed out.")
