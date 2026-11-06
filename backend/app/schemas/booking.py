from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import BookingStatus, PaymentStatus
from app.schemas.common import OptionalText, ORMModel, PersonName, Phone


class StaySearch(BaseModel):
    check_in: date
    check_out: date
    adults: int = Field(ge=1, le=6)
    children: int = Field(default=0, ge=0, le=4)


class RoomQuote(BaseModel):
    slug: str
    name: str
    summary: str
    image_url: str
    image_alt: str
    size_label: str
    bed_label: str
    view_label: str
    occupancy_label: str
    is_signature: bool
    fits_party: bool              # fits in a single room
    room_count: int               # rooms of this type the party needs (the price covers all of them)
    max_rooms: int                # most rooms of this type bookable now (free rooms, capped per booking)
    available_rooms: int
    bookable: bool
    nights: int
    nightly_rate_paise: int               # standard / double-occupancy rate per room
    single_rate_paise: int | None = None  # single-occupancy rate, if any
    single_rooms: int = 0                 # rooms of this quote charged the single rate
    nightly_total_paise: int = 0          # all rooms, one night
    inclusions: str = ""
    subtotal_paise: int
    tax_percent: Decimal
    tax_paise: int
    total_paise: int
    currency: str


class AvailabilityResult(BaseModel):
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    rooms: list[RoomQuote]


class BookingCreate(StaySearch):
    room_type_slug: str = Field(min_length=1, max_length=60)
    # Rooms of that type; defaults to the fewest that sleep the party
    room_count: int | None = Field(default=None, ge=1, le=10)
    guest_name: PersonName
    guest_email: EmailStr = Field(max_length=255)
    guest_phone: Phone
    special_requests: OptionalText = Field(default=None, max_length=1000)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please accept the booking terms to continue")
        return v


class CheckoutPrefill(BaseModel):
    name: str
    email: str
    contact: str


class CheckoutConfig(BaseModel):
    """Everything Razorpay Checkout needs. Contains the public key id only."""

    key_id: str
    # "mock" tells the site to show the test-payment window instead of Razorpay Checkout
    mode: Literal["razorpay", "mock"] = "razorpay"
    order_id: str
    amount: int
    currency: str
    name: str
    description: str
    prefill: CheckoutPrefill


class BookingPublic(ORMModel):
    reference: str
    status: BookingStatus
    room_type_slug: str
    room_type_name: str
    room_count: int = 1
    room_image_url: str
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    guest_name: str
    guest_email: str
    guest_phone: str
    special_requests: str | None
    nightly_rate_paise: int
    single_room_count: int = 0
    single_rate_paise: int | None = None
    inclusions: str | None = None
    subtotal_paise: int
    tax_percent: Decimal
    tax_paise: int
    total_paise: int
    currency: str
    hold_expires_at: datetime | None
    confirmed_at: datetime | None
    payment_status: PaymentStatus | None
    created_at: datetime
    cancellation_policy: str | None = None


class BookingCheckout(BaseModel):
    booking: BookingPublic
    checkout: CheckoutConfig | None


class BookingLookup(BaseModel):
    reference: str = Field(min_length=6, max_length=16)
    email: EmailStr

    @field_validator("reference")
    @classmethod
    def _ref(cls, v: str) -> str:
        return v.strip().upper()


class PaymentVerify(BaseModel):
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]{6,40}$")
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]{6,40}$")
    razorpay_signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class PaymentClientReport(BaseModel):
    """What the browser saw when checkout closed without success. Recorded for
    support only - it never changes a payment's status."""

    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]{6,40}$")
    outcome: str = Field(pattern=r"^(dismissed|failed)$")
    razorpay_payment_id: str | None = Field(default=None, pattern=r"^pay_[A-Za-z0-9]{6,40}$")
    error_code: str | None = Field(default=None, max_length=64)
    error_description: str | None = Field(default=None, max_length=500)


class MockCheckoutIn(BaseModel):
    """Test payment mode only: what the simulated customer did in the payment window."""

    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]{6,40}$")
    outcome: Literal["success", "failure"]


class PaymentResult(BaseModel):
    booking: BookingPublic
    message: str
