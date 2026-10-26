"""Admin > Roles & access: define roles and the permissions each one grants.
Reading roles needs users.manage (to assign them); changing them needs
roles.manage, which only the Administrator role holds."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.permissions import IMPLIES, NON_ASSIGNABLE, PERMISSION_INFO, Permission
from app.db.session import get_db
from app.models import AdminUser, Role
from app.schemas.admin import PermissionInfoOut, RoleIn, RoleOut, RoleUpdate
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["Admin: roles & access"])
VIEW = require(Permission.USERS_MANAGE)
MANAGE = require(Permission.ROLES_MANAGE)


def _out(role: Role, counts: dict[int, int]) -> RoleOut:
    out = RoleOut.model_validate(role)
    perms = [p.value for p in PERMISSION_INFO] if role.is_system else out.permissions
    return out.model_copy(update={"user_count": counts.get(role.id, 0), "permissions": perms})


@router.get("", response_model=list[RoleOut])
def list_roles(_: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
    counts = role_service.user_counts(db)
    roles = db.execute(select(Role).order_by(Role.is_system.desc(), Role.name)).scalars().all()
    return [_out(r, counts) for r in roles]


@router.get("/permissions", response_model=list[PermissionInfoOut], summary="Grantable permissions, grouped")
def permission_catalogue(_: AdminUser = Depends(VIEW)):
    return [PermissionInfoOut(key=p.value, group=g, label=label, description=d,
                              implies=sorted(i.value for i in IMPLIES.get(p, ())))
            for p, (g, label, d) in PERMISSION_INFO.items() if p not in NON_ASSIGNABLE]


@router.post("", response_model=RoleOut, status_code=201)
def create_role(data: RoleIn, request: Request, actor: AdminUser = Depends(MANAGE), db: Session = Depends(get_db)):
    role = role_service.create(db, name=data.name, description=data.description, permissions=data.permissions,
                               actor=actor, request=request)
    return _out(role, {})


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(role_id: int, data: RoleUpdate, request: Request, actor: AdminUser = Depends(MANAGE),
                db: Session = Depends(get_db)):
    role = role_service.update(db, role_id, changes=data.model_dump(exclude_unset=True), actor=actor, request=request)
    return _out(role, role_service.user_counts(db))


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, request: Request, actor: AdminUser = Depends(MANAGE), db: Session = Depends(get_db)):
    role_service.delete(db, role_id, actor=actor, request=request)
    return Response(status_code=204)
