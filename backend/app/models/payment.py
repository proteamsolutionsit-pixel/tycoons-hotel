from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base, TimestampMixin, enum_col
from app.models.enums import PaymentStatus

if TYPE_CHECKING:
    from app.models.booking import Booking


class Payment(TimestampMixin, Base):
    """One Razorpay order. A guest may make several attempts against the same
    order (Razorpay allows retries); the row tracks the latest attempt and the
    final outcome. No card data is ever stored."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), index=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[PaymentStatus] = mapped_column(enum_col(PaymentStatus), default=PaymentStatus.CREATED)
    method: Mapped[str | None] = mapped_column(String(32))
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_description: Mapped[str | None] = mapped_column(String(500))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime)
    razorpay_refund_id: Mapped[str | None] = mapped_column(String(64))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime)

    booking: Mapped["Booking"] = relationship(back_populates="payments")


class PaymentEvent(Base):
    """Audit log of everything that touched a payment: webhooks (deduplicated
    by Razorpay's event id), checkout callbacks, reconciliations."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # x-razorpay-event-id
    source: Mapped[str] = mapped_column(String(16))       # webhook | verify | client | reconcile | admin
    event_type: Mapped[str] = mapped_column(String(64))
    razorpay_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[Any] = mapped_column(JSON)
    result: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
