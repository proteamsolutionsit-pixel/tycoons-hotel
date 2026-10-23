"""Staff sessions, password-reset tokens, the audit trail and the shared
rate-limit counters."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base


class AdminSession(Base):
    """Server-side staff session. The browser holds only an opaque random
    token; the database keeps its SHA-256, so a leaked table cannot be replayed."""

    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_user_active", "user_id", "revoked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)          # absolute lifetime
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_reason: Mapped[str | None] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_ip: Mapped[str | None] = mapped_column(String(45))


class AuditLog(Base):
    """Append-only record of administrative actions and security events.
    UPDATE and DELETE are rejected by database triggers (see migration), and
    the restricted runtime DB account has only SELECT/INSERT on this table."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_actor", "actor_id", "occurred_at"),
        Index("ix_audit_logs_action", "action", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(16))        # admin | system | guest | anonymous
    actor_id: Mapped[int | None] = mapped_column(Integer)      # no FK: survives user deletion
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64))            # e.g. booking.cancel, auth.login_failed
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16))           # success | failure | denied
    ip: Mapped[str | None] = mapped_column(String(45))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[Any] = mapped_column(JSON, nullable=True)  # safe, non-secret context only


class RateLimitBucket(Base):
    """Fixed-window counters shared by every API worker and host."""

    __tablename__ = "rate_limit_buckets"

    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(scope|identity)
    hits: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
