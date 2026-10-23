"""Room availability and bookings (guests do not sign in; a booking is
identified by its reference plus the email used to make it)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.rate_limit import enforce, rate_limit
from app.db.session import get_db
from app.schemas.booking import AvailabilityResult, BookingCheckout, BookingCreate, BookingLookup, BookingPublic
from app.services import booking_service
from app.services.razorpay_gateway import PaymentGateway, get_gateway

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/availability", response_model=AvailabilityResult,
            dependencies=[Depends(rate_limit("availability", 60, 60))],
            summary="Rooms, live availability and server-calculated prices for a stay")
def availability(check_in: date, check_out: date, adults: int = Query(2, ge=1, le=6),
                 children: int = Query(0, ge=0, le=4), db: Session = Depends(get_db)):
    return booking_service.search(db, check_in, check_out, adults, children)


@router.post("", response_model=BookingCheckout, status_code=201,
             summary="Hold a room and create the Razorpay order to pay for it")
def create_booking(data: BookingCreate, request: Request,
                   idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),
                   db: Session = Depends(get_db), gateway: PaymentGateway | None = Depends(get_gateway)):
    enforce(request, "booking-create", 10, 600)
    if idempotency_key is not None and (len(idempotency_key) < 16 or not idempotency_key.replace("-", "").isalnum()):
        raise AppError("Invalid Idempotency-Key header.", code="invalid_idempotency_key")
    if gateway is None:
        raise AppError("Online payment is not available right now. Please contact reservations.",
                       code="payments_unavailable", status_code=503)
    booking, payment = booking_service.create_booking(db, data, idempotency_key, gateway)
    return BookingCheckout(booking=booking_service.to_public(booking),
                           checkout=booking_service.checkout_config(booking, payment, gateway))


@router.post("/lookup", response_model=BookingPublic, summary="Find a booking by reference and email")
def lookup(data: BookingLookup, request: Request, db: Session = Depends(get_db)):
    enforce(request, "booking-lookup", 20, 600)
    # Also per booking, across all IPs: stops distributed guessing of the email for a reference
    enforce(request, "booking-lookup-ref", 10, 600, extra_key=data.reference, per_ip=False)
    return booking_service.to_public(booking_service.find_for_guest(db, data.reference, str(data.email)))


@router.post("/{reference}/payment", response_model=BookingCheckout,
             summary="Re-open checkout for an unpaid booking (same order, while the hold lasts)")
def retry_payment(reference: str, data: BookingLookup, request: Request, db: Session = Depends(get_db),
                  gateway: PaymentGateway | None = Depends(get_gateway)):
    enforce(request, "booking-lookup", 20, 600)
    enforce(request, "booking-lookup-ref", 10, 600, extra_key=data.reference, per_ip=False)
    if data.reference != reference.strip().upper():
        raise AppError("Reference mismatch.", code="reference_mismatch")
    if gateway is None:
        raise AppError("Online payment is not available right now.", code="payments_unavailable", status_code=503)
    booking = booking_service.find_for_guest(db, data.reference, str(data.email))
    payment = booking_service.ensure_order(db, booking, gateway)
    db.refresh(booking)
    return BookingCheckout(booking=booking_service.to_public(booking),
                           checkout=booking_service.checkout_config(booking, payment, gateway))
