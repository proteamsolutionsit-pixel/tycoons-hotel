"""Audit trail.

`record()` adds the entry to the caller's session, so it commits (or rolls
back) together with the change it describes. `record_now()` writes in its own
transaction, for events that must survive a failed request: login failures,
permission denials, rejected webhook signatures.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog

log = logging.getLogger("app.audit")

_SENSITIVE = re.compile(r"pass|secret|token|signature|authorization|cookie|card|cvv|otp", re.I)


def _clean(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        return {str(k)[:64]: ("[redacted]" if _SENSITIVE.search(str(k)) else _clean(v, depth + 1))
                for k, v in list(value.items())[:40]}
    if isinstance(value, list | tuple):
        return [_clean(v, depth + 1) for v in list(value)[:40]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)[:500]


def _context(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    return ip, getattr(request.state, "request_id", None)


def build(*, action: str, outcome: str = "success", actor: AdminUser | None = None, actor_type: str | None = None,
          actor_email: str | None = None, resource_type: str | None = None, resource_id: Any = None,
          details: dict | None = None, request: Request | None = None) -> AuditLog:
    ip, rid = _context(request)
    return AuditLog(
        actor_type=actor_type or ("admin" if actor else "anonymous"),
        actor_id=actor.id if actor else None,
        actor_email=(actor.email if actor else actor_email),
        action=action, outcome=outcome, resource_type=resource_type,
        resource_id=None if resource_id is None else str(resource_id)[:64],
        ip=ip, request_id=rid, details=_clean(details) if details else None,
    )


def record(db: Session, **kwargs) -> AuditLog:
    entry = build(**kwargs)
    db.add(entry)
    return entry


def record_now(**kwargs) -> None:
    """Independent transaction; never raises (an audit failure must not turn a
    401 into a 500, but it is logged loudly)."""
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            db.add(build(**kwargs))
            db.commit()
    except Exception:
        log.exception("Could not write audit record", extra={"action": kwargs.get("action")})
