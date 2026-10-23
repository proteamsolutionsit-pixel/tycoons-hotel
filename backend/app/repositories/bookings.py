from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models import Booking, Payment
from app.models.enums import BookingStatus

# Statuses that occupy inventory (pending ones only while their hold lasts)
_OCCUPYING = (BookingStatus.CONFIRMED,)


# Booking eagerly joins room_types; `of=Booking` keeps FOR UPDATE from also
# locking the room type row (which would stall other checkouts for that room).

def get_by_reference(db: Session, reference: str, *, for_update: bool = False) -> Booking | None:
    stmt = select(Booking).where(Booking.reference == reference)
    if for_update:
        stmt = stmt.with_for_update(of=Booking)
    return db.execute(stmt).unique().scalar_one_or_none()


def get_by_idempotency_key(db: Session, key: str) -> Booking | None:
    return db.execute(select(Booking).where(Booking.idempotency_key == key)).unique().scalar_one_or_none()


def lock(db: Session, booking_id: int) -> Booking:
    return db.execute(select(Booking).where(Booking.id == booking_id).with_for_update(of=Booking)
                      .execution_options(populate_existing=True)).unique().scalar_one()


def overlapping_stays(db: Session, room_type_id: int, check_in: date, check_out: date, now: datetime,
                      exclude_booking_id: int | None = None) -> list[tuple[date, date]]:
    """Stays of this room type that overlap [check_in, check_out) and hold a room."""
    stmt = select(Booking.check_in, Booking.check_out).where(
        Booking.room_type_id == room_type_id,
        Booking.check_in < check_out,
        Booking.check_out > check_in,
        or_(
            Booking.status.in_(_OCCUPYING),
            and_(Booking.status == BookingStatus.PENDING_PAYMENT, Booking.hold_expires_at > now),
        ),
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(Booking.id != exclude_booking_id)
    return [(r.check_in, r.check_out) for r in db.execute(stmt)]


def expire_stale_holds(db: Session, now: datetime, room_type_id: int | None = None) -> int:
    """Mark pending bookings whose hold has lapsed as expired. A capture that
    arrives later is still honoured if a room is free (see payment_service)."""
    stmt = (
        update(Booking)
        .where(Booking.status == BookingStatus.PENDING_PAYMENT, Booking.hold_expires_at <= now)
        .values(status=BookingStatus.EXPIRED, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if room_type_id is not None:
        stmt = stmt.where(Booking.room_type_id == room_type_id)
    return db.execute(stmt).rowcount or 0


def latest_payment(booking: Booking) -> Payment | None:
    return booking.payments[-1] if booking.payments else None
