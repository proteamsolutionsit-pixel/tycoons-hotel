"""Payment verification, webhooks, reconciliation and refunds.

Rules
  * The browser's checkout response is untrusted until its signature is
    verified with the key secret.
  * A booking becomes CONFIRMED only when its payment is CAPTURED for the
    exact amount and currency of the order - confirmed either by fetching the
    payment from Razorpay after a valid checkout signature, or by a webhook
    whose signature verifies against the raw body.
  * Every handler is idempotent: replays, duplicate webhooks and verify/webhook
    races leave the same final state. Rows are locked payment -> booking ->
    room type, always in that order.
  * A status never moves backwards (a late `payment.failed` cannot undo a capture).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound, UpstreamError
from app.core.timeutil import utcnow
from app.models import Booking, Payment, RoomType
from app.models.enums import BookingStatus, PaymentStatus
from app.repositories import bookings as booking_repo
from app.repositories import payments as payment_repo
from app.schemas.booking import PaymentClientReport, PaymentVerify
from app.services import availability
from app.services.razorpay_gateway import GatewayError, PaymentGateway

log = logging.getLogger("app.payments")

_SETTLED = (PaymentStatus.CAPTURED, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED)


@dataclass
class Outcome:
    booking: Booking | None = None
    newly_confirmed: bool = False
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)


# -- Core state transitions -------------------------------------------------

def _matches(payment: Payment, entity: dict[str, Any]) -> bool:
    return (entity.get("order_id") == payment.razorpay_order_id
            and int(entity.get("amount", -1)) == payment.amount_paise
            and str(entity.get("currency", "")).upper() == payment.currency)


def _mark_captured(db: Session, payment: Payment, entity: dict[str, Any], out: Outcome) -> None:
    """payment is already locked by the caller."""
    if payment.status in _SETTLED:
        out.notes.append("already_captured")
        return
    payment.status = PaymentStatus.CAPTURED
    payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
    payment.method = (entity.get("method") or payment.method or "")[:32] or None
    payment.captured_at = utcnow()
    payment.error_code = payment.error_description = None

    booking = booking_repo.lock(db, payment.booking_id)
    out.booking = booking
    now = utcnow()
    if booking.status == BookingStatus.CONFIRMED:
        out.notes.append("booking_already_confirmed")
        return

    if booking.status == BookingStatus.PENDING_PAYMENT and booking.hold_expires_at and booking.hold_expires_at > now:
        _confirm(booking, now, out)
        return

    if booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.EXPIRED):
        # The hold lapsed before the money arrived. Honour it if a room is still free.
        room = db.execute(select(RoomType).where(RoomType.id == booking.room_type_id).with_for_update()).scalar_one()
        if availability.available_rooms(db, room, booking.check_in, booking.check_out, now,
                                        exclude_booking_id=booking.id) >= 1:
            _confirm(booking, now, out)
            out.notes.append("confirmed_after_hold_lapsed")
            return

    booking.status = BookingStatus.PAYMENT_REVIEW
    booking.hold_expires_at = None
    out.needs_review = True
    out.notes.append("payment_review")
    log.warning("Captured payment needs review", extra={"booking": booking.reference,
                                                        "order": payment.razorpay_order_id})


def _confirm(booking: Booking, now, out: Outcome) -> None:
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = now
    booking.hold_expires_at = None
    out.newly_confirmed = True
    log.info("Booking confirmed", extra={"booking": booking.reference})


def _mark_authorized(payment: Payment, entity: dict[str, Any]) -> None:
    if payment.status in _SETTLED:
        return
    payment.status = PaymentStatus.AUTHORIZED
    payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
    payment.method = (entity.get("method") or payment.method or "")[:32] or None


def _mark_failed(payment: Payment, entity: dict[str, Any]) -> None:
    if payment.status in _SETTLED or (payment.status == PaymentStatus.AUTHORIZED
                                      and entity.get("id") not in (None, payment.razorpay_payment_id)):
        # A failed retry must not hide an earlier attempt that did go through.
        return
    payment.status = PaymentStatus.FAILED
    payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
    payment.error_code = (entity.get("error_code") or "")[:64] or None
    payment.error_description = (entity.get("error_description") or "")[:500] or None


def _apply_gateway_payment(db: Session, gateway: PaymentGateway, payment: Payment, entity: dict[str, Any],
                           out: Outcome) -> None:
    """Act on a payment entity fetched from (or pushed by) Razorpay."""
    if not _matches(payment, entity):
        out.notes.append("amount_or_order_mismatch")
        log.error("Razorpay payment does not match order", extra={"order": payment.razorpay_order_id,
                                                                  "payment": entity.get("id")})
        return
    status = entity.get("status")
    if status == "captured":
        _mark_captured(db, payment, entity, out)
    elif status == "authorized":
        # Accounts with automatic capture never get here; otherwise capture now.
        try:
            captured = gateway.capture_payment(entity["id"], payment.amount_paise, payment.currency)
        except GatewayError:
            _mark_authorized(payment, entity)
            out.notes.append("capture_failed")
            return
        if captured.get("status") == "captured" and _matches(payment, captured):
            _mark_captured(db, payment, captured, out)
        else:
            _mark_authorized(payment, entity)
    elif status == "failed":
        _mark_failed(payment, entity)
    elif status == "refunded":
        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = payment.refunded_at or utcnow()


# -- Checkout callback ------------------------------------------------------

def verify_checkout(db: Session, data: PaymentVerify, gateway: PaymentGateway | None) -> Outcome:
    if gateway is None:
        raise AppError("Online payment is not available right now.", code="payments_unavailable", status_code=503)
    payment = payment_repo.get_by_order_id(db, data.razorpay_order_id, for_update=True)
    if payment is None:
        db.rollback()
        raise NotFound("Payment not found.", code="payment_not_found")

    valid = gateway.verify_payment_signature(data.razorpay_order_id, data.razorpay_payment_id,
                                             data.razorpay_signature)
    payment_repo.record_event(db, source="verify", event_type="checkout.success",
                              order_id=data.razorpay_order_id, payment_id=data.razorpay_payment_id,
                              payload={"signature_valid": valid},
                              result="ok" if valid else "invalid_signature")
    if not valid:
        db.commit()
        log.warning("Invalid checkout signature", extra={"order": data.razorpay_order_id})
        raise AppError("We could not verify this payment. If money was deducted, it will be confirmed "
                       "automatically or refunded.", code="payment_verification_failed")

    out = Outcome()
    payment.signature_verified = True
    if payment.status not in _SETTLED:
        _mark_authorized(payment, {"id": data.razorpay_payment_id})
        try:
            entity = gateway.fetch_payment(data.razorpay_payment_id)
        except GatewayError:
            entity = None
            out.notes.append("fetch_failed_await_webhook")
        if entity is not None:
            _apply_gateway_payment(db, gateway, payment, entity, out)

    out.booking = out.booking or booking_repo.lock(db, payment.booking_id)
    db.commit()
    db.refresh(out.booking)
    return out


def record_client_report(db: Session, data: PaymentClientReport) -> None:
    """Checkout closed without success. Logged for support; changes nothing."""
    payment = payment_repo.get_by_order_id(db, data.razorpay_order_id)
    if payment is None:
        raise NotFound("Payment not found.", code="payment_not_found")
    payment_repo.record_event(db, source="client", event_type=f"checkout.{data.outcome}",
                              order_id=data.razorpay_order_id, payment_id=data.razorpay_payment_id,
                              payload=data.model_dump(), result="recorded")
    db.commit()


# -- Webhooks ---------------------------------------------------------------

def handle_webhook(db: Session, raw_body: bytes, signature: str, event_id: str | None,
                   gateway: PaymentGateway | None) -> Outcome:
    if gateway is None:
        raise AppError("Payments are not configured.", code="payments_unavailable", status_code=503)
    if not gateway.verify_webhook_signature(raw_body, signature):
        log.warning("Webhook signature rejected")
        raise AppError("Invalid signature.", code="invalid_signature", status_code=400)

    try:
        event = json.loads(raw_body)
    except ValueError:
        raise AppError("Invalid payload.", code="invalid_payload", status_code=400)
    event_type = str(event.get("event", ""))[:64]
    payload = event.get("payload") or {}
    pay_entity = (payload.get("payment") or {}).get("entity") or {}
    order_entity = (payload.get("order") or {}).get("entity") or {}
    refund_entity = (payload.get("refund") or {}).get("entity") or {}
    order_id = pay_entity.get("order_id") or order_entity.get("id")
    # Razorpay sends a unique x-razorpay-event-id per event; fall back to a body hash.
    event_id = (event_id or "sha256:" + hashlib.sha256(raw_body).hexdigest()[:56])[:64]

    ev = payment_repo.record_event(db, source="webhook", event_type=event_type, payload=event,
                                   order_id=order_id, payment_id=pay_entity.get("id") or refund_entity.get("payment_id"),
                                   event_id=event_id)
    out = Outcome()
    if ev is None:
        db.rollback()
        out.notes.append("duplicate")
        return out

    payment: Payment | None = None
    if order_id:
        payment = payment_repo.get_by_order_id(db, order_id, for_update=True)
    elif refund_entity.get("payment_id"):
        payment = db.execute(select(Payment).where(Payment.razorpay_payment_id == refund_entity["payment_id"])
                             .with_for_update()).scalar_one_or_none()

    if payment is None:
        ev.result = "unknown_order"
        db.commit()
        return out

    if event_type in ("payment.captured", "order.paid"):
        entity = dict(pay_entity)
        entity.setdefault("status", "captured")
        if event_type == "order.paid" and not entity.get("order_id"):
            entity["order_id"] = order_id
        if _matches(payment, entity):
            _mark_captured(db, payment, entity, out)
        else:
            out.notes.append("amount_or_order_mismatch")
    elif event_type == "payment.authorized":
        if _matches(payment, pay_entity):
            _mark_authorized(payment, pay_entity)
    elif event_type == "payment.failed":
        _mark_failed(payment, pay_entity)
    elif event_type == "refund.processed":
        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = utcnow()
        payment.razorpay_refund_id = refund_entity.get("id") or payment.razorpay_refund_id
    elif event_type == "refund.failed":
        if payment.status == PaymentStatus.REFUND_PENDING:
            payment.status = PaymentStatus.CAPTURED
        out.notes.append("refund_failed")
    else:
        out.notes.append("ignored")

    ev.result = ",".join(out.notes)[:255] or "applied"
    if out.booking is None:
        out.booking = payment.booking
    db.commit()
    return out


# -- Reconciliation & refunds ----------------------------------------------

def reconcile(db: Session, payment_id: int, gateway: PaymentGateway | None) -> Outcome:
    """Ask Razorpay what really happened to an order and apply it. Used by the
    admin 'Reconcile' button and `python -m app.cli reconcile`."""
    if gateway is None:
        raise AppError("Payments are not configured.", code="payments_unavailable", status_code=503)
    payment = payment_repo.lock(db, payment_id)
    try:
        attempts = gateway.fetch_order_payments(payment.razorpay_order_id)
    except GatewayError as exc:
        db.rollback()
        raise UpstreamError("Could not reach Razorpay. Try again shortly.", code="reconcile_failed") from exc

    out = Outcome()
    rank = {"captured": 0, "refunded": 1, "authorized": 2, "failed": 3}
    attempts = sorted(attempts, key=lambda a: rank.get(a.get("status"), 9))
    if attempts:
        _apply_gateway_payment(db, gateway, payment, attempts[0], out)
    else:
        out.notes.append("no_attempts")
    payment_repo.record_event(db, source="reconcile", event_type="reconcile", order_id=payment.razorpay_order_id,
                              payment_id=payment.razorpay_payment_id,
                              payload={"attempts": [{k: a.get(k) for k in ("id", "status", "amount")} for a in attempts]},
                              result=",".join(out.notes)[:255] or "no_change")
    out.booking = out.booking or payment.booking
    db.commit()
    return out


def cancel_booking(db: Session, booking_id: int, reason: str, refund: bool,
                   gateway: PaymentGateway | None) -> Booking:
    booking = booking_repo.lock(db, booking_id)
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.EXPIRED):
        db.rollback()
        raise Conflict("This booking is already closed.", code="already_closed")

    captured = next((p for p in reversed(booking.payments) if p.status == PaymentStatus.CAPTURED), None)
    if captured and refund:
        if gateway is None:
            db.rollback()
            raise AppError("Payments are not configured, so no refund can be issued.", code="payments_unavailable",
                           status_code=503)
        payment_repo.lock(db, captured.id)
        try:
            res = gateway.refund_payment(captured.razorpay_payment_id, captured.amount_paise,
                                         {"booking_reference": booking.reference, "reason": reason[:200]})
        except GatewayError as exc:
            db.rollback()
            raise UpstreamError("Razorpay refused the refund. Nothing was changed.", code="refund_failed") from exc
        captured.status = PaymentStatus.REFUNDED if res.get("status") == "processed" else PaymentStatus.REFUND_PENDING
        captured.razorpay_refund_id = res.get("id")
        if captured.status == PaymentStatus.REFUNDED:
            captured.refunded_at = utcnow()
        payment_repo.record_event(db, source="admin", event_type="refund.created", order_id=captured.razorpay_order_id,
                                  payment_id=captured.razorpay_payment_id,
                                  payload={"refund_id": res.get("id"), "status": res.get("status")}, result="ok")

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = utcnow()
    booking.cancel_reason = reason[:255]
    booking.hold_expires_at = None
    db.commit()
    db.refresh(booking)
    return booking
