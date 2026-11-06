"""Stay validation, inventory and pricing. All amounts are integer paise and
come from the database - never from the client."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.timeutil import hotel_today
from app.models import RoomType
from app.repositories import bookings as booking_repo


@dataclass(frozen=True)
class Quote:
    nights: int
    nightly_rate_paise: int        # standard / double-occupancy rate per room
    single_rate_paise: int | None  # single-occupancy rate, if the room type has one
    single_rooms: int              # rooms charged at the single rate
    nightly_total_paise: int       # all rooms, one night
    subtotal_paise: int
    tax_percent: Decimal
    tax_paise: int
    total_paise: int


def validate_stay(check_in: date, check_out: date) -> int:
    s = get_settings()
    today = hotel_today()
    if check_in < today:
        raise AppError("Check-in cannot be in the past.", code="invalid_dates",
                       details=[{"field": "check_in", "message": "Choose today or a later date"}])
    if check_out <= check_in:
        raise AppError("Check-out must be after check-in.", code="invalid_dates",
                       details=[{"field": "check_out", "message": "Choose a date after check-in"}])
    nights = (check_out - check_in).days
    if nights > s.max_stay_nights:
        raise AppError(f"Online bookings are limited to {s.max_stay_nights} nights. Please contact us for longer stays.",
                       code="stay_too_long", details=[{"field": "check_out", "message": "Stay is too long"}])
    if check_in > today + timedelta(days=s.max_advance_days):
        raise AppError(f"Bookings open {s.max_advance_days} days in advance.", code="too_far_ahead",
                       details=[{"field": "check_in", "message": "Date is too far ahead"}])
    return nights


def fits_party(room: RoomType, adults: int, children: int, rooms: int = 1) -> bool:
    """The party fits in `rooms` rooms of this type, with at least one adult per room."""
    return rooms <= adults and adults <= room.max_adults * rooms and children <= room.max_children * rooms


def rooms_needed(room: RoomType, adults: int, children: int) -> int | None:
    """Fewest rooms of this type that sleep the party (None if it can't, within the per-booking cap)."""
    for n in range(1, get_settings().max_rooms_per_booking + 1):
        if fits_party(room, adults, children, n):
            return n
    return None


def peak_occupancy(stays, check_in: date, check_out: date) -> int:
    """Highest number of rooms taken on any single night of the stay.
    `stays` are (check_in, check_out[, rooms]) tuples; rooms defaults to 1."""
    peak = 0
    night = check_in
    while night < check_out:
        taken = sum((s[2] if len(s) > 2 else 1) for s in stays if s[0] <= night < s[1])
        peak = max(peak, taken)
        night += timedelta(days=1)
    return peak


def available_rooms(db: Session, room: RoomType, check_in: date, check_out: date, now: datetime,
                    exclude_booking_id: int | None = None) -> int:
    stays = booking_repo.overlapping_stays(db, room.id, check_in, check_out, now, exclude_booking_id)
    return max(0, room.total_rooms - peak_occupancy(stays, check_in, check_out))


def occupancy_split(adults: int, rooms: int) -> list[int]:
    """Adults per room, spread as evenly as possible (3 adults in 2 rooms -> [2, 1])."""
    base, extra = divmod(adults, rooms)
    return [base + 1] * extra + [base] * (rooms - extra)


def quote(room: RoomType, nights: int, tax_percent: Decimal, rooms: int = 1, adults: int | None = None) -> Quote:
    """Rates are per room per night: a room holding one adult is charged the
    single-occupancy rate when the room type has one, otherwise the standard rate.
    Children do not change the occupancy rate. Without `adults`, every room is standard."""
    single = room.single_rate_paise
    singles = 0
    if single is not None and adults is not None:
        singles = sum(1 for a in occupancy_split(adults, rooms) if a == 1)
    nightly_total = room.base_rate_paise * (rooms - singles) + (single or 0) * singles
    subtotal = nightly_total * nights
    tax = int((Decimal(subtotal) * tax_percent / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return Quote(nights=nights, nightly_rate_paise=room.base_rate_paise, single_rate_paise=single,
                 single_rooms=singles, nightly_total_paise=nightly_total, subtotal_paise=subtotal,
                 tax_percent=tax_percent, tax_paise=tax, total_paise=subtotal + tax)
