from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SiteSetting

# Settings used by business logic, never sent to the public site
PRIVATE_KEYS = {"room_tax_percent"}


def all_settings(db: Session) -> list[SiteSetting]:
    return list(db.execute(select(SiteSetting).order_by(SiteSetting.group, SiteSetting.sort_order)).scalars())


def public_settings(db: Session) -> dict[str, Any]:
    return {s.key: s.value for s in all_settings(db) if s.key not in PRIVATE_KEYS}


def get_value(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(SiteSetting, key)
    return default if row is None else row.value


def room_tax_percent(db: Session) -> Decimal:
    raw = get_value(db, "room_tax_percent", 0)
    try:
        pct = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return pct if Decimal("0") <= pct <= Decimal("100") else Decimal("0")
