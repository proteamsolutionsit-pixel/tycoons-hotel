"""The booking and payment state machines - the single definition of which
status changes are legal. Services change statuses only through
`move_booking()` / `move_payment()`; anything else is a bug and raises.

Booking
    pending_payment ──capture──▶ confirmed ──cancel──▶ cancelled
          │  └──hold lapses──▶ expired ──late capture, room free──▶ confirmed
          │                       └──late capture, room gone──▶ payment_review
          └──cancel──▶ cancelled ──capture arrives anyway──▶ payment_review
    payment_review ──staff rehouse──▶ confirmed | ──refund/cancel──▶ cancelled

Payment
    created ─▶ authorized ─▶ captured ─▶ refund_pending ─▶ refunded
       └─▶ failed ─▶ (retry on the same order) authorized | captured | failed
    refund_pending ─▶ captured  (refund failed at Razorpay)
"""
from __future__ import annotations

import logging

from app.models import Booking, Payment
from app.models.enums import BookingStatus as B
from app.models.enums import PaymentStatus as P

log = logging.getLogger("app.states")


class IllegalTransition(RuntimeError):
    pass


BOOKING_TRANSITIONS: dict[B, frozenset[B]] = {
    B.PENDING_PAYMENT: frozenset({B.CONFIRMED, B.EXPIRED, B.CANCELLED, B.PAYMENT_REVIEW}),
    B.EXPIRED: frozenset({B.CONFIRMED, B.PAYMENT_REVIEW}),
    B.CONFIRMED: frozenset({B.CANCELLED}),
    B.PAYMENT_REVIEW: frozenset({B.CONFIRMED, B.CANCELLED}),
    B.CANCELLED: frozenset({B.PAYMENT_REVIEW}),
}

PAYMENT_TRANSITIONS: dict[P, frozenset[P]] = {
    P.CREATED: frozenset({P.AUTHORIZED, P.CAPTURED, P.FAILED}),
    P.FAILED: frozenset({P.AUTHORIZED, P.CAPTURED, P.FAILED}),
    P.AUTHORIZED: frozenset({P.CAPTURED, P.FAILED}),
    P.CAPTURED: frozenset({P.REFUND_PENDING, P.REFUNDED}),
    P.REFUND_PENDING: frozenset({P.REFUNDED, P.CAPTURED}),
    P.REFUNDED: frozenset(),
}

# Payment states that mean money was taken and must not be overwritten by a later failure event
SETTLED = frozenset({P.CAPTURED, P.REFUND_PENDING, P.REFUNDED})


def can_move_booking(current: B, new: B) -> bool:
    return new == current or new in BOOKING_TRANSITIONS.get(current, frozenset())


def can_move_payment(current: P, new: P) -> bool:
    return new == current or new in PAYMENT_TRANSITIONS.get(current, frozenset())


def move_booking(booking: Booking, new: B) -> bool:
    """Apply a transition. Returns False if already in that state."""
    if booking.status == new:
        return False
    if not can_move_booking(booking.status, new):
        log.error("Illegal booking transition", extra={"booking": booking.reference,
                                                       "from": booking.status.value, "to": new.value})
        raise IllegalTransition(f"booking {booking.status.value} -> {new.value}")
    booking.status = new
    return True


def move_payment(payment: Payment, new: P) -> bool:
    if payment.status == new:
        return False
    if not can_move_payment(payment.status, new):
        log.error("Illegal payment transition", extra={"order": payment.razorpay_order_id,
                                                       "from": payment.status.value, "to": new.value})
        raise IllegalTransition(f"payment {payment.status.value} -> {new.value}")
    payment.status = new
    return True
