"""Room booking: availability search, holds, and Razorpay order creation.

Flow
  1. create_booking() validates the stay, locks the room type row, re-checks
     inventory and inserts a PENDING_PAYMENT booking that holds a room for
     BOOKING_HOLD_MINUTES. The price is computed here from the database.
  2. ensure_order() creates (or reuses) the Razorpay order for that booking.
  3. payment_service confirms the booking only after a verified capture.
"""
from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound, UpstreamError
from app.core.timeutil import utcnow
from app.domain.states import move_booking
from app.models import Booking, Payment, RoomType
from app.models.enums import BookingStatus, PaymentStatus
from app.repositories import bookings as booking_repo
from app.repositories import settings as settings_repo
from app.schemas.booking import (
    AvailabilityResult,
    BookingCreate,
    BookingPublic,
    CheckoutConfig,
    CheckoutPrefill,
    RoomQuote,
)
from app.services import availability
from app.services.razorpay_gateway import GatewayError, PaymentGateway

log = logging.getLogger("app.booking")

_REF_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"  # no 0/O, 1/I/L, U  # pragma: allowlist secret


def new_reference() -> str:
    return "TYC" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(8))


def to_public(b: Booking) -> BookingPublic:
    p = booking_repo.latest_payment(b)
    return BookingPublic(
        reference=b.reference, status=b.status, room_type_slug=b.room_type.slug, room_type_name=b.room_type.name,
        room_image_url=b.room_type.image_url, check_in=b.check_in, check_out=b.check_out, nights=b.nights,
        adults=b.adults, children=b.children, guest_name=b.guest_name, guest_email=b.guest_email,
        guest_phone=b.guest_phone, special_requests=b.special_requests, nightly_rate_paise=b.nightly_rate_paise,
        subtotal_paise=b.subtotal_paise, tax_percent=b.tax_percent, tax_paise=b.tax_paise,
        total_paise=b.total_paise, currency=b.currency, hold_expires_at=b.hold_expires_at,
        confirmed_at=b.confirmed_at, payment_status=p.status if p else None, created_at=b.created_at,
        cancellation_policy=b.cancellation_policy,
    )


# -- Search ---------------------------------------------------------------

def search(db: Session, check_in: date, check_out: date, adults: int, children: int) -> AvailabilityResult:
    nights = availability.validate_stay(check_in, check_out)
    now = utcnow()
    tax = settings_repo.room_tax_percent(db)
    currency = get_settings().currency
    rooms = db.execute(select(RoomType).where(RoomType.is_active.is_(True))
                       .order_by(RoomType.sort_order, RoomType.id)).scalars().all()
    stays = booking_repo.overlapping_stays_by_room(db, [r.id for r in rooms], check_in, check_out, now)
    quotes = []
    for room in rooms:
        free = max(0, room.total_rooms - availability.peak_occupancy(stays[room.id], check_in, check_out))
        fits = availability.fits_party(room, adults, children)
        q = availability.quote(room, nights, tax)
        quotes.append(RoomQuote(
            slug=room.slug, name=room.name, summary=room.summary, image_url=room.image_url,
            image_alt=room.image_alt, size_label=room.size_label, bed_label=room.bed_label,
            view_label=room.view_label, occupancy_label=room.occupancy_label, is_signature=room.is_signature,
            fits_party=fits, available_rooms=free, bookable=fits and free > 0, nights=nights,
            nightly_rate_paise=q.nightly_rate_paise, subtotal_paise=q.subtotal_paise, tax_percent=q.tax_percent,
            tax_paise=q.tax_paise, total_paise=q.total_paise, currency=currency,
        ))
    return AvailabilityResult(check_in=check_in, check_out=check_out, nights=nights, adults=adults,
                              children=children, rooms=quotes)


# -- Create ---------------------------------------------------------------

def _same_request(b: Booking, data: BookingCreate) -> bool:
    return (b.room_type.slug == data.room_type_slug and b.check_in == data.check_in
            and b.check_out == data.check_out and b.guest_email.lower() == str(data.guest_email).lower())


def create_booking(db: Session, data: BookingCreate, idempotency_key: str | None,
                   gateway: PaymentGateway | None) -> tuple[Booking, Payment]:
    if gateway is None:
        raise AppError("Online payment is not available right now. Please contact reservations.",
                       code="payments_unavailable", status_code=503)

    if idempotency_key:
        existing = booking_repo.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            if not _same_request(existing, data):
                raise Conflict("This checkout was already used for a different booking.", code="idempotency_mismatch")
            return existing, ensure_order(db, existing, gateway)

    s = get_settings()
    nights = availability.validate_stay(data.check_in, data.check_out)
    now = utcnow()

    # Lock the room type: concurrent checkouts for it queue here, so the
    # inventory check below and the insert are atomic.
    room = db.execute(select(RoomType).where(RoomType.slug == data.room_type_slug, RoomType.is_active.is_(True))
                      .with_for_update()).scalar_one_or_none()
    if room is None:
        db.rollback()
        raise NotFound("That room type is not available.", code="room_not_found")
    if not availability.fits_party(room, data.adults, data.children):
        db.rollback()
        raise AppError(f"The {room.name} sleeps up to {room.max_adults} adults and {room.max_children} "
                       f"{'child' if room.max_children == 1 else 'children'}.", code="party_too_large")

    booking_repo.expire_stale_holds(db, now, room.id)
    if availability.available_rooms(db, room, data.check_in, data.check_out, now) < 1:
        db.rollback()
        raise Conflict(f"Sorry, the {room.name} is no longer available for those dates.", code="sold_out")

    q = availability.quote(room, nights, settings_repo.room_tax_percent(db))
    booking = Booking(
        reference=new_reference(), idempotency_key=idempotency_key, room_type_id=room.id,
        check_in=data.check_in, check_out=data.check_out, nights=nights, adults=data.adults,
        children=data.children, guest_name=data.guest_name, guest_email=str(data.guest_email).lower(),
        guest_phone=data.guest_phone, special_requests=data.special_requests,
        nightly_rate_paise=q.nightly_rate_paise, subtotal_paise=q.subtotal_paise, tax_percent=q.tax_percent,
        tax_paise=q.tax_paise, total_paise=q.total_paise, currency=s.currency,
        status=BookingStatus.PENDING_PAYMENT, hold_expires_at=now + timedelta(minutes=s.booking_hold_minutes),
        # What the guest agreed to, as shown to them at booking time
        terms_version=str(settings_repo.get_value(db, "booking_terms_version", "") or "")[:32] or None,
        terms_accepted_at=now,
        cancellation_policy=str(settings_repo.get_value(db, "cancellation_policy", "") or "") or None,
    )
    db.add(booking)
    try:
        db.commit()  # hold acquired; lock released
    except IntegrityError as exc:
        db.rollback()
        # Same idempotency key raced us, or (astronomically unlikely) a reference clash
        if idempotency_key and (existing := booking_repo.get_by_idempotency_key(db, idempotency_key)):
            return existing, ensure_order(db, existing, gateway)
        raise Conflict("Please try again.", code="retry") from exc
    db.refresh(booking)
    log.info("Booking held", extra={"booking": booking.reference, "room": room.slug, "total_paise": q.total_paise})

    try:
        payment = ensure_order(db, booking, gateway)
    except UpstreamError:
        # No order, so no way to pay: release the room immediately.
        booking = booking_repo.lock(db, booking.id)
        move_booking(booking, BookingStatus.CANCELLED)
        booking.cancelled_at = utcnow()
        booking.cancel_reason = "Payment order could not be created"
        booking.hold_expires_at = None
        db.commit()
        raise
    return booking, payment


def ensure_order(db: Session, booking: Booking, gateway: PaymentGateway) -> Payment:
    """Return a payable Razorpay order for a pending booking, creating one if
    needed. Razorpay lets a guest retry several times on the same order, so an
    existing created/failed order is reused rather than duplicated."""
    booking = booking_repo.lock(db, booking.id)
    now = utcnow()
    if booking.status == BookingStatus.CONFIRMED:
        db.rollback()
        raise Conflict("This booking is already paid and confirmed.", code="already_paid")
    if booking.status != BookingStatus.PENDING_PAYMENT or (booking.hold_expires_at and booking.hold_expires_at <= now):
        db.rollback()
        raise Conflict("This booking has expired. Please search again to rebook.", code="booking_expired")

    for p in reversed(booking.payments):
        if p.amount_paise == booking.total_paise and p.status in (PaymentStatus.CREATED, PaymentStatus.FAILED):
            db.commit()
            return p
        if p.status == PaymentStatus.AUTHORIZED:
            db.rollback()
            raise Conflict("A payment for this booking is already being processed. Please wait a moment.",
                           code="payment_in_progress")

    try:
        order = gateway.create_order(
            amount=booking.total_paise, currency=booking.currency, receipt=booking.reference,
            notes={"booking_reference": booking.reference, "booking_id": str(booking.id)},
        )
    except GatewayError as exc:
        db.rollback()
        raise UpstreamError("We could not start the payment. Please try again in a moment.",
                            code="payment_order_failed") from exc

    if int(order.get("amount", -1)) != booking.total_paise or order.get("currency") != booking.currency:
        db.rollback()
        log.error("Razorpay order amount mismatch", extra={"booking": booking.reference, "order": order.get("id")})
        raise UpstreamError("We could not start the payment. Please try again.", code="payment_order_failed")

    payment = Payment(booking_id=booking.id, razorpay_order_id=order["id"], amount_paise=booking.total_paise,
                      currency=booking.currency, status=PaymentStatus.CREATED)
    db.add(payment)
    db.commit()
    db.refresh(booking)
    log.info("Razorpay order created", extra={"booking": booking.reference, "order": order["id"]})
    return payment


def checkout_config(booking: Booking, payment: Payment, gateway: PaymentGateway) -> CheckoutConfig:
    s = get_settings()
    return CheckoutConfig(
        key_id=gateway.key_id, order_id=payment.razorpay_order_id, amount=payment.amount_paise,
        currency=payment.currency, name=s.hotel_name,
        description=f"{booking.room_type.name} · {booking.nights} night{'s' if booking.nights != 1 else ''}",
        prefill=CheckoutPrefill(name=booking.guest_name, email=booking.guest_email, contact=booking.guest_phone),
    )


def find_for_guest(db: Session, reference: str, email: str) -> Booking:
    b = booking_repo.get_by_reference(db, reference)
    if b is None or b.guest_email.lower() != email.strip().lower():
        # One message for both cases, so references can't be probed
        raise NotFound("We couldn't find a booking with that reference and email.", code="booking_not_found")
    now = utcnow()
    if b.status == BookingStatus.PENDING_PAYMENT and b.hold_expires_at and b.hold_expires_at <= now:
        booking_repo.expire_stale_holds(db, now, b.room_type_id)
        db.commit()
        db.refresh(b)
    return b
