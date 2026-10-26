"""Time helpers.

Timestamps are stored in the database as naive UTC DATETIMEs (the DB session
is pinned to +00:00). Calendar dates that belong to the hotel (check-in,
reservation dates) are plain DATEs in the hotel's timezone.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def utcnow() -> datetime:
    """Naive UTC 'now', matching how DATETIME columns are stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hotel_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().hotel_timezone)


def hotel_today() -> date:
    return datetime.now(hotel_tz()).date()


def hotel_day_start_utc(day: date) -> datetime:
    """Midnight at the hotel on `day`, as naive UTC (for filtering DATETIME columns)."""
    local = datetime(day.year, day.month, day.day, tzinfo=hotel_tz())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def to_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
