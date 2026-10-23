from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric,
                        String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_col
from app.models.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.room import RoomType


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("check_out > check_in", name="dates_ordered"),
        CheckConstraint("adults >= 1", name="adults_positive"),
        CheckConstraint("children >= 0", name="children_non_negative"),
        CheckConstraint("total_paise >= 0", name="total_non_negative"),
        # Availability lookups: overlapping stays of one room type in a live status
        Index("ix_bookings_availability", "room_type_id", "status", "check_in", "check_out"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True)
    # Client-supplied key so a double-submitted checkout never creates two bookings
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)

    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id", ondelete="RESTRICT"))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer)
    adults: Mapped[int] = mapped_column(Integer)
    children: Mapped[int] = mapped_column(Integer, default=0)

    guest_name: Mapped[str] = mapped_column(String(120))
    guest_email: Mapped[str] = mapped_column(String(255), index=True)
    guest_phone: Mapped[str] = mapped_column(String(32))
    special_requests: Mapped[str | None] = mapped_column(Text)

    # Price snapshot taken from the database at booking time
    nightly_rate_paise: Mapped[int] = mapped_column(Integer)
    subtotal_paise: Mapped[int] = mapped_column(Integer)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    tax_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    status: Mapped[BookingStatus] = mapped_column(enum_col(BookingStatus), default=BookingStatus.PENDING_PAYMENT)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))

    room_type: Mapped["RoomType"] = relationship(lazy="joined")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", order_by="Payment.id")
