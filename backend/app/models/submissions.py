"""Guest-submitted requests from the site's forms. None of these are paid;
staff follow up by phone or email and track progress with `status`."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_col
from app.models.enums import EnquiryKind, GuestType, SubmissionStatus

if TYPE_CHECKING:
    from app.models.content import JobOpening, SpaTreatment


class _Tracked:
    status: Mapped[SubmissionStatus] = mapped_column(enum_col(SubmissionStatus, 16), default=SubmissionStatus.NEW,
                                                     index=True)
    staff_notes: Mapped[str | None] = mapped_column(Text)


class TableReservation(_Tracked, TimestampMixin, Base):
    """Fishy Tales > Reserve a table."""

    __tablename__ = "table_reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    reservation_date: Mapped[date] = mapped_column(Date, index=True)
    reservation_time: Mapped[time] = mapped_column(Time)
    party_size: Mapped[str] = mapped_column(String(8))     # "2", "3", "4", "5-8", "9+"
    occasion: Mapped[str] = mapped_column(String(32))
    special_requests: Mapped[str | None] = mapped_column(Text)


class SpaAppointment(_Tracked, TimestampMixin, Base):
    """Kai Wellness Spa > Book a treatment."""

    __tablename__ = "spa_appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    # NULL means "Not sure - advise me"
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("spa_treatments.id", ondelete="SET NULL"))
    guest_type: Mapped[GuestType] = mapped_column(enum_col(GuestType, 16))
    preferred_date: Mapped[date] = mapped_column(Date, index=True)
    preferred_time: Mapped[time] = mapped_column(Time)

    treatment: Mapped["SpaTreatment | None"] = relationship(lazy="joined")


class Enquiry(_Tracked, TimestampMixin, Base):
    """Contact > Send enquiry (kind=contact) and Business Lounge > Plan your
    business stay (kind=business)."""

    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[EnquiryKind] = mapped_column(enum_col(EnquiryKind, 16), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    topic: Mapped[str | None] = mapped_column(String(40))         # contact
    company: Mapped[str | None] = mapped_column(String(160))      # business
    arrival_date: Mapped[date | None] = mapped_column(Date)       # business
    guests: Mapped[int | None] = mapped_column(Integer)           # business
    message: Mapped[str | None] = mapped_column(Text)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)


class JobApplication(_Tracked, TimestampMixin, Base):
    """Careers > Send your application. The CV is stored outside any web root."""

    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    opening_id: Mapped[int | None] = mapped_column(ForeignKey("job_openings.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    position: Mapped[str] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(Text)
    cv_path: Mapped[str | None] = mapped_column(String(255))          # relative to STORAGE_DIR/private
    cv_original_name: Mapped[str | None] = mapped_column(String(255))
    cv_content_type: Mapped[str | None] = mapped_column(String(100))
    cv_size: Mapped[int | None] = mapped_column(Integer)
    consent: Mapped[bool] = mapped_column(Boolean)

    opening: Mapped["JobOpening | None"] = relationship(lazy="joined")


class NewsletterSubscriber(TimestampMixin, Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime)
