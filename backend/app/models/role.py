"""Access roles: a named set of permissions that administrators define in
Admin > Roles & access and assign to staff users.

The Administrator role (is_system) always has every permission, including
ones added in later versions, and cannot be edited or deleted."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ADMINISTRATOR_KEY = "administrator"
FRONT_DESK_KEY = "front_desk"


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable handle for the built-in roles (NULL for roles created in the admin)
    key: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
