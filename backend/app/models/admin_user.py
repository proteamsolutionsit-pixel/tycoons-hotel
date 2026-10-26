from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_col
from app.models.enums import AdminRole
from app.models.role import Role


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Legacy two-level role, kept in step with access_role: ADMIN exactly when the
    # user holds the Administrator role (used for the last-administrator guard).
    role: Mapped[AdminRole] = mapped_column(enum_col(AdminRole, 16), default=AdminRole.STAFF)
    # The access role that decides what this user may do (Admin > Roles & access)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    access_role: Mapped[Role | None] = relationship(lazy="joined")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Legacy (JWT sessions, replaced by admin_sessions in 1.1). Kept so the
    # migration stays additive; no longer read.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def role_name(self) -> str:
        if self.access_role is not None:
            return self.access_role.name
        return "Administrator" if self.role == AdminRole.ADMIN else "Front desk"
