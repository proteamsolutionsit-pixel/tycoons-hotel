"""Schemas for the staff admin API."""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import (
    AdminRole,
    BookingStatus,
    CardSection,
    EnquiryKind,
    GalleryCategory,
    GalleryLayout,
    GuestType,
    PaymentStatus,
    SubmissionStatus,
)
from app.schemas.common import ORMModel


class StrictInput(BaseModel):
    """Admin request bodies: unknown fields are rejected (no mass assignment)."""

    model_config = ConfigDict(extra="forbid")


_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
# Image URLs: site assets (/assets/...), uploads (/media/...) or https.
_IMAGE_URL = r"^(/assets/|/media/|https://)[^\s<>\"']{1,490}$"


# -- Auth / users ------------------------------------------------------------

class LoginIn(StrictInput):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AdminUserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: AdminRole                 # legacy: "admin" exactly when role_name is Administrator
    role_id: int | None
    role_name: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class MeOut(AdminUserOut):
    permissions: list[str] = []


class AdminUserCreate(StrictInput):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    # The access role; `role` ("admin"/"staff") is still accepted and means the
    # built-in Administrator / Front desk roles. role_id wins when both are sent.
    role_id: int | None = None
    role: AdminRole = AdminRole.STAFF
    password: str = Field(min_length=12, max_length=128)


class AdminUserUpdate(StrictInput):
    email: EmailStr | None = None              # the sign-in name; must stay unique
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role_id: int | None = None
    role: AdminRole | None = None
    is_active: bool | None = None


# -- Roles & access ------------------------------------------------------------
class PermissionInfoOut(BaseModel):
    key: str
    group: str
    label: str
    description: str
    implies: list[str]


class RoleOut(ORMModel):
    id: int
    key: str | None
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    user_count: int = 0
    updated_at: datetime


class RoleIn(StrictInput):
    name: str = Field(min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list, max_length=50)


class RoleUpdate(StrictInput):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = Field(default=None, max_length=50)


class PasswordChange(StrictInput):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordReset(StrictInput):
    new_password: str = Field(min_length=12, max_length=128)


# -- Bookings / payments ---------------------------------------------------

class PaymentOut(ORMModel):
    id: int
    razorpay_order_id: str
    razorpay_payment_id: str | None
    amount_paise: int
    currency: str
    status: PaymentStatus
    method: str | None
    signature_verified: bool
    error_code: str | None
    error_description: str | None
    captured_at: datetime | None
    razorpay_refund_id: str | None
    refunded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentRow(PaymentOut):
    booking_reference: str
    guest_name: str


class PaymentEventOut(ORMModel):
    id: int
    source: str
    event_type: str
    razorpay_payment_id: str | None
    result: str | None
    created_at: datetime


class BookingRow(ORMModel):
    id: int
    reference: str
    status: BookingStatus
    room_type_name: str
    room_count: int = 1
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    guest_name: str
    guest_email: str
    guest_phone: str
    total_paise: int
    currency: str
    payment_status: PaymentStatus | None
    created_at: datetime


class BookingDetail(BookingRow):
    special_requests: str | None
    nightly_rate_paise: int
    subtotal_paise: int
    tax_percent: Decimal
    tax_paise: int
    hold_expires_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    terms_version: str | None
    terms_accepted_at: datetime | None
    cancellation_policy: str | None
    payments: list[PaymentOut]
    events: list[PaymentEventOut]


class CancelIn(StrictInput):
    reason: str = Field(min_length=3, max_length=255)
    refund: bool = False
    # Required with refund=true: must equal the captured amount. Guards against
    # refunding the wrong booking from a stale screen.
    confirm_refund_paise: int | None = Field(default=None, ge=1)


class ConfirmReviewIn(StrictInput):
    note: str = Field(min_length=3, max_length=255)


class AuditLogOut(ORMModel):
    id: int
    occurred_at: datetime
    actor_type: str
    actor_id: int | None
    actor_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    ip: str | None
    request_id: str | None
    details: Any | None


class OccupancyRoom(BaseModel):
    slug: str
    name: str
    total_rooms: int
    booked: list[int]       # per day: confirmed + payment review
    held: list[int]         # per day: unpaid holds still active


class Occupancy(BaseModel):
    start: date
    days: list[date]
    rooms: list[OccupancyRoom]


# -- Catalogue / content ---------------------------------------------------

class RoomTypeBase(StrictInput):
    name: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4000)
    image_url: str = Field(pattern=_IMAGE_URL)
    image_alt: str = Field(default="", max_length=200)
    size_label: str = Field(default="", max_length=120)
    bed_label: str = Field(default="", max_length=120)
    view_label: str = Field(default="", max_length=120)
    occupancy_label: str = Field(default="", max_length=120)
    max_adults: int = Field(ge=1, le=10)
    max_children: int = Field(ge=0, le=10)
    base_rate_paise: int = Field(ge=100, le=100_000_000, description="Per night, before tax, in paise")
    total_rooms: int = Field(ge=0, le=1000)
    is_signature: bool = False
    sort_order: int = 0
    is_active: bool = True


class RoomTypeCreate(RoomTypeBase):
    slug: str = Field(min_length=2, max_length=60, pattern=_SLUG)


class RoomTypeUpdate(StrictInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    summary: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    image_url: str | None = Field(default=None, pattern=_IMAGE_URL)
    image_alt: str | None = Field(default=None, max_length=200)
    size_label: str | None = Field(default=None, max_length=120)
    bed_label: str | None = Field(default=None, max_length=120)
    view_label: str | None = Field(default=None, max_length=120)
    occupancy_label: str | None = Field(default=None, max_length=120)
    max_adults: int | None = Field(default=None, ge=1, le=10)
    max_children: int | None = Field(default=None, ge=0, le=10)
    base_rate_paise: int | None = Field(default=None, ge=100, le=100_000_000)
    total_rooms: int | None = Field(default=None, ge=0, le=1000)
    is_signature: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class RoomTypeOut(RoomTypeCreate, ORMModel):
    id: int
    updated_at: datetime


class SpaTreatmentCreate(StrictInput):
    slug: str = Field(min_length=2, max_length=60, pattern=_SLUG)
    name: str = Field(min_length=2, max_length=120)
    form_label: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    image_url: str = Field(pattern=_IMAGE_URL)
    image_alt: str = Field(default="", max_length=200)
    duration_label: str = Field(default="", max_length=60)
    price_label: str = Field(default="", max_length=60)
    sort_order: int = 0
    is_active: bool = True


class SpaTreatmentUpdate(StrictInput):
    slug: str | None = Field(default=None, min_length=2, max_length=60, pattern=_SLUG)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    form_label: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    image_url: str | None = Field(default=None, pattern=_IMAGE_URL)
    image_alt: str | None = Field(default=None, max_length=200)
    duration_label: str | None = Field(default=None, max_length=60)
    price_label: str | None = Field(default=None, max_length=60)
    sort_order: int | None = None
    is_active: bool | None = None


class SpaTreatmentOut(SpaTreatmentCreate, ORMModel):
    id: int


class ContentCardCreate(StrictInput):
    section: CardSection
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=2000)
    image_url: str = Field(pattern=_IMAGE_URL)
    image_alt: str = Field(default="", max_length=200)
    meta: str | None = Field(default=None, max_length=200)
    sort_order: int = 0
    is_active: bool = True


class ContentCardUpdate(StrictInput):
    section: CardSection | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    image_url: str | None = Field(default=None, pattern=_IMAGE_URL)
    image_alt: str | None = Field(default=None, max_length=200)
    meta: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None
    is_active: bool | None = None


class ContentCardOut(ContentCardCreate, ORMModel):
    id: int


class GalleryImageCreate(StrictInput):
    image_url: str = Field(pattern=_IMAGE_URL)
    alt: str = Field(min_length=1, max_length=200)
    category: GalleryCategory
    layout: GalleryLayout = GalleryLayout.NORMAL
    width: int | None = Field(default=None, ge=1, le=20000)
    height: int | None = Field(default=None, ge=1, le=20000)
    on_home: bool = False
    home_order: int = 0
    sort_order: int = 0
    is_active: bool = True


class GalleryImageUpdate(StrictInput):
    image_url: str | None = Field(default=None, pattern=_IMAGE_URL)
    alt: str | None = Field(default=None, min_length=1, max_length=200)
    category: GalleryCategory | None = None
    layout: GalleryLayout | None = None
    width: int | None = Field(default=None, ge=1, le=20000)
    height: int | None = Field(default=None, ge=1, le=20000)
    on_home: bool | None = None
    home_order: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class GalleryImageOut(GalleryImageCreate, ORMModel):
    id: int


class JobOpeningCreate(StrictInput):
    title: str = Field(min_length=2, max_length=160)
    department: str = Field(min_length=1, max_length=120)
    employment_type: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=4000)
    sort_order: int = 0
    is_active: bool = True


class JobOpeningUpdate(StrictInput):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    department: str | None = Field(default=None, min_length=1, max_length=120)
    employment_type: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=4000)
    sort_order: int | None = None
    is_active: bool | None = None


class JobOpeningOut(JobOpeningCreate, ORMModel):
    id: int


class SettingOut(ORMModel):
    key: str
    value: Any
    label: str
    group: str
    help_text: str | None
    updated_at: datetime


class SettingUpdate(StrictInput):
    value: Any

    @field_validator("value")
    @classmethod
    def _size(cls, v: Any) -> Any:
        import json
        if len(json.dumps(v)) > 20000:
            raise ValueError("Value is too large")
        return v


# -- Submissions -----------------------------------------------------------

class SubmissionUpdate(StrictInput):
    status: SubmissionStatus | None = None
    staff_notes: str | None = Field(default=None, max_length=4000)


class _SubmissionBase(ORMModel):
    id: int
    status: SubmissionStatus
    staff_notes: str | None
    created_at: datetime


class TableReservationOut(_SubmissionBase):
    name: str
    phone: str
    reservation_date: date
    reservation_time: time
    party_size: str
    occasion: str
    special_requests: str | None


class SpaAppointmentOut(_SubmissionBase):
    name: str
    phone: str
    treatment_id: int | None
    treatment_name: str | None = None
    guest_type: GuestType
    preferred_date: date
    preferred_time: time


class EnquiryOut(_SubmissionBase):
    kind: EnquiryKind
    name: str
    email: str
    phone: str | None
    topic: str | None
    company: str | None
    arrival_date: date | None
    guests: int | None
    message: str | None
    consent: bool


class JobApplicationOut(_SubmissionBase):
    opening_id: int | None
    name: str
    email: str
    phone: str
    position: str
    message: str | None
    cv_original_name: str | None
    cv_size: int | None
    has_cv: bool = False


class NewsletterOut(ORMModel):
    id: int
    email: str
    is_active: bool
    consent_at: datetime
    unsubscribed_at: datetime | None
    created_at: datetime


class NewsletterUpdate(StrictInput):
    is_active: bool


class Dashboard(BaseModel):
    arrivals_today: int
    departures_today: int
    arrivals_next_7_days: int
    in_house_tonight: int
    rooms_total: int
    rooms_sold_tonight: int
    occupancy_tonight_pct: float
    pending_payment: int
    payment_review: int
    revenue_30d_paise: int
    refunded_30d_paise: int
    confirmed_30d: int
    new_submissions: dict[str, int]
    alerts: dict[str, int]   # payment discrepancies / security signals, all counts


class UploadOut(BaseModel):
    url: str
    size: int


# -- Payment gateway settings ------------------------------------------------
class PaymentSettingsOut(BaseModel):
    """What is in force. Secrets are never returned - only whether one is set."""

    mode: Literal["mock", "razorpay"]
    active: Literal["mock", "test", "live", "disabled"]
    source: Literal["admin", "environment"]
    key_id: str
    key_kind: Literal["test", "live"] | None
    has_key_secret: bool
    has_webhook_secret: bool
    secrets_readable: bool
    environment: str
    mock_allowed: bool
    webhook_url: str
    updated_at: datetime | None
    updated_by: str | None


class PaymentSettingsUpdate(StrictInput):
    mode: Literal["mock", "razorpay"]
    key_id: str = Field(default="", max_length=64)
    # Blank keeps the stored secret
    key_secret: str | None = Field(default=None, max_length=128)
    webhook_secret: str | None = Field(default=None, max_length=128)
    confirm_live: bool = False


class PaymentSettingsTest(StrictInput):
    key_id: str = Field(default="", max_length=64)
    key_secret: str | None = Field(default=None, max_length=128)


class PaymentSettingsTestResult(BaseModel):
    ok: bool
    message: str
