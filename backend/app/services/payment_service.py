"""Payment verification, webhooks, reconciliation and refunds.

Rules
  * The browser's checkout response is untrusted until its signature verifies
    with the key secret; even then the booking is confirmed only after the
    payment is fetched from Razorpay (or pushed by a verified webhook) as
    CAPTURED for the exact order, amount and currency.
  * Webhooks are verified against the raw body and deduplicated by
    x-razorpay-event-id. Checkout callbacks and webhooks may arrive in any
    order; every handler is idempotent.
  * Status changes go through app.domain.states (never backwards).
  * Rows are locked payment -> booking -> room type, always in that order.
  * Razorpay calls cannot share a DB transaction. Refunds therefore write an
    intent record first; if the process dies after Razorpay accepted the
    refund, the refund webhook or `reconcile` completes the local state.
  * Stored event payloads are reduced to ids, amounts and statuses - never
    the customer contact details Razorpay includes.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound, UpstreamError
from app.core.timeutil import utcnow
from app.domain.states import SETTLED, move_booking, move_payment
from app.models import AdminUser, Booking, Payment, RoomType
from app.models.enums import BookingStatus, PaymentStatus
from app.repositories import bookings as booking_repo
from app.repositories import payments as payment_repo
from app.schemas.booking import PaymentClientReport, PaymentVerify
from app.services import audit, availability
from app.services.razorpay_gateway import GatewayError, PaymentGateway

log = logging.getLogger("app.payments")

_PAY_KEYS = ("id", "order_id", "amount", "currency", "status", "method", "captured", "error_code",
             "error_reason", "error_source", "error_step", "error_description", "refund_status", "amount_refunded")
_ORDER_KEYS = ("id", "amount", "amount_paid", "currency", "status", "receipt", "attempts")
_REFUND_KEYS = ("id", "payment_id", "amount", "currency", "status", "speed_processed")


def redact_entity(entity: dict | None, keys: tuple[str, ...]) -> dict | None:
    if not entity:
        return None
    return {k: entity[k] for k in keys if k in entity}


@dataclass
class Outcome:
    booking: Booking | None = None
    newly_confirmed: bool = False
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def confirmed_booking(self) -> Booking:
        """The booking for flows that always load it (verify, reconcile)."""
        if self.booking is None:
            raise RuntimeError("payment outcome has no booking")
        return self.booking


def _require_gateway(gateway: PaymentGateway | None) -> PaymentGateway:
    if gateway is None:
        raise AppError("Online payment is not available right now.", code="payments_unavailable", status_code=503)
    return gateway


# -- Core state transitions -------------------------------------------------

def _matches(payment: Payment, entity: dict[str, Any]) -> bool:
    return (entity.get("order_id") == payment.razorpay_order_id
            and int(entity.get("amount", -1)) == payment.amount_paise
            and str(entity.get("currency", "")).upper() == payment.currency)


def _confirm(booking: Booking, out: Outcome) -> None:
    move_booking(booking, BookingStatus.CONFIRMED)
    booking.confirmed_at = utcnow()
    booking.hold_expires_at = None
    out.newly_confirmed = True
    log.info("Booking confirmed", extra={"booking": booking.reference})


def _mark_captured(db: Session, payment: Payment, entity: dict[str, Any], out: Outcome) -> None:
    """`payment` is already locked by the caller."""
    if payment.status in SETTLED:
        out.notes.append("already_captured")
        return
    move_payment(payment, PaymentStatus.CAPTURED)
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
        _confirm(booking, out)
        return

    if booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.EXPIRED):
        # The hold lapsed before the money arrived: honour it if a room is still free.
        room = db.execute(select(RoomType).where(RoomType.id == booking.room_type_id).with_for_update()).scalar_one()
        if availability.available_rooms(db, room, booking.check_in, booking.check_out, now,
                                        exclude_booking_id=booking.id) >= 1:
            _confirm(booking, out)
            out.notes.append("confirmed_after_hold_lapsed")
            return

    # Room gone, or the booking had been cancelled: money taken, staff must act.
    move_booking(booking, BookingStatus.PAYMENT_REVIEW)
    booking.hold_expires_at = None
    out.needs_review = True
    out.notes.append("payment_review")
    log.error("Captured payment needs review", extra={"alert": "payment_review", "booking": booking.reference,
                                                      "order": payment.razorpay_order_id})


def _mark_authorized(payment: Payment, entity: dict[str, Any]) -> None:
    if payment.status in SETTLED or payment.status == PaymentStatus.AUTHORIZED:
        return
    move_payment(payment, PaymentStatus.AUTHORIZED)
    payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
    payment.method = (entity.get("method") or payment.method or "")[:32] or None


def _mark_failed(payment: Payment, entity: dict[str, Any]) -> None:
    if payment.status in SETTLED or (payment.status == PaymentStatus.AUTHORIZED
                                     and entity.get("id") not in (None, payment.razorpay_payment_id)):
        # A failed retry must not hide an earlier attempt that did go through.
        return
    move_payment(payment, PaymentStatus.FAILED)
    payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
    payment.error_code = (entity.get("error_code") or "")[:64] or None
    payment.error_description = (entity.get("error_description") or "")[:500] or None


def _mark_refunded(db: Session, payment: Payment, refund_id: str | None, out: Outcome) -> None:
    if payment.status == PaymentStatus.REFUNDED:
        out.notes.append("already_refunded")
        return
    if payment.status not in (PaymentStatus.CAPTURED, PaymentStatus.REFUND_PENDING):
        out.notes.append("refund_for_uncaptured_payment")
        return
    move_payment(payment, PaymentStatus.REFUNDED)
    payment.refunded_at = utcnow()
    payment.razorpay_refund_id = refund_id or payment.razorpay_refund_id
    booking = db.get(Booking, payment.booking_id)
    out.booking = booking
    if booking is not None and booking.status in (BookingStatus.CONFIRMED, BookingStatus.PAYMENT_REVIEW):
        # Refunded outside this app (Razorpay dashboard) while the stay is still booked.
        out.notes.append("refunded_while_booking_active")
        log.error("Payment refunded while booking still active",
                  extra={"alert": "refund_booking_active", "booking": booking.reference})


def _apply_gateway_payment(db: Session, gateway: PaymentGateway, payment: Payment, entity: dict[str, Any],
                           out: Outcome) -> None:
    """Act on a payment entity fetched from (or pushed by) Razorpay."""
    if not _matches(payment, entity):
        out.notes.append("amount_or_order_mismatch")
        log.error("Razorpay payment does not match order", extra={"alert": "payment_mismatch",
                                                                  "order": payment.razorpay_order_id,
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
        _mark_refunded(db, payment, None, out)


# -- Checkout callback ------------------------------------------------------

def verify_checkout(db: Session, data: PaymentVerify, gateway: PaymentGateway | None) -> Outcome:
    gateway = _require_gateway(gateway)
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
    if payment.status not in SETTLED:
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
                              payload={"outcome": data.outcome, "error_code": data.error_code,
                                       "error_description": data.error_description}, result="recorded")
    db.commit()


# -- Webhooks ---------------------------------------------------------------

def handle_webhook(db: Session, raw_body: bytes, signature: str, event_id: str | None,
                   gateway: PaymentGateway | None, request: Request | None = None) -> Outcome:
    gateway = _require_gateway(gateway)
    if not gateway.verify_webhook_signature(raw_body, signature):
        log.warning("Webhook signature rejected", extra={"alert": "webhook_signature"})
        audit.record_now(action="security.webhook_signature_rejected", outcome="denied", actor_type="anonymous",
                         details={"event_id": (event_id or "")[:64], "bytes": len(raw_body)}, request=request)
        raise AppError("Invalid signature.", code="invalid_signature", status_code=400)

    try:
        event = json.loads(raw_body)
    except ValueError as exc:
        raise AppError("Invalid payload.", code="invalid_payload", status_code=400) from exc
    event_type = str(event.get("event", ""))[:64]
    payload = event.get("payload") or {}
    pay_entity = (payload.get("payment") or {}).get("entity") or {}
    order_entity = (payload.get("order") or {}).get("entity") or {}
    refund_entity = (payload.get("refund") or {}).get("entity") or {}
    order_id = pay_entity.get("order_id") or order_entity.get("id")
    # Razorpay sends a unique x-razorpay-event-id per event; fall back to a body hash.
    event_id = (event_id or "sha256:" + hashlib.sha256(raw_body).hexdigest()[:56])[:64]

    summary = {"event": event_type, "payment": redact_entity(pay_entity, _PAY_KEYS),
               "order": redact_entity(order_entity, _ORDER_KEYS), "refund": redact_entity(refund_entity, _REFUND_KEYS)}
    ev = payment_repo.record_event(db, source="webhook", event_type=event_type, payload=summary,
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
        log.warning("Webhook for unknown order", extra={"alert": "webhook_unknown_order", "event": event_type})
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
            log.error("Webhook amount mismatch", extra={"alert": "payment_mismatch", "order": order_id})
    elif event_type == "payment.authorized":
        if _matches(payment, pay_entity):
            _mark_authorized(payment, pay_entity)
    elif event_type == "payment.failed":
        _mark_failed(payment, pay_entity)
    elif event_type == "refund.processed":
        _mark_refunded(db, payment, refund_entity.get("id"), out)
    elif event_type == "refund.failed":
        if payment.status == PaymentStatus.REFUND_PENDING:
            move_payment(payment, PaymentStatus.CAPTURED)
        out.notes.append("refund_failed")
        log.error("Refund failed at Razorpay", extra={"alert": "refund_failed", "order": payment.razorpay_order_id})
    else:
        out.notes.append("ignored")

    ev.result = ",".join(out.notes)[:255] or "applied"
    if out.booking is None:
        out.booking = payment.booking
    db.commit()
    return out


# -- Reconciliation ------------------------------------------------------------

def reconcile(db: Session, payment_id: int, gateway: PaymentGateway | None,
              actor: AdminUser | None = None, request: Request | None = None) -> Outcome:
    """Ask Razorpay what really happened to an order and apply it."""
    gateway = _require_gateway(gateway)
    payment = payment_repo.lock(db, payment_id)
    try:
        attempts = gateway.fetch_order_payments(payment.razorpay_order_id)
    except GatewayError as exc:
        db.rollback()
        log.error("Reconciliation failed", extra={"alert": "reconcile_failed", "order": payment.razorpay_order_id})
        raise UpstreamError("Could not reach Razorpay. Try again shortly.", code="reconcile_failed") from exc

    out = Outcome()
    rank = {"captured": 0, "refunded": 1, "authorized": 2, "failed": 3}
    attempts = sorted(attempts, key=lambda a: rank.get(str(a.get("status")), 9))
    if attempts:
        _apply_gateway_payment(db, gateway, payment, attempts[0], out)
    else:
        out.notes.append("no_attempts")
    payment_repo.record_event(db, source="reconcile", event_type="reconcile", order_id=payment.razorpay_order_id,
                              payment_id=payment.razorpay_payment_id,
                              payload={"attempts": [{k: a.get(k) for k in ("id", "status", "amount")} for a in attempts]},
                              result=",".join(out.notes)[:255] or "no_change")
    out.booking = out.booking or payment.booking
    if actor is not None:
        audit.record(db, action="payment.reconcile", actor=actor, resource_type="payment", resource_id=payment.id,
                     details={"order": payment.razorpay_order_id, "result": out.notes,
                              "booking_status": out.booking.status.value}, request=request)
    db.commit()
    return out


# -- Staff actions: cancel / refund / resolve review ---------------------------

def _captured_payment(booking: Booking) -> Payment | None:
    return next((p for p in reversed(booking.payments) if p.status == PaymentStatus.CAPTURED), None)


def cancel_booking(db: Session, booking_id: int, *, reason: str, refund: bool, confirm_refund_paise: int | None,
                   gateway: PaymentGateway | None, actor: AdminUser, request: Request | None = None) -> Booking:
    booking = booking_repo.lock(db, booking_id)
    if booking.status not in (BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED, BookingStatus.PAYMENT_REVIEW):
        db.rollback()
        raise Conflict("This booking is already closed.", code="already_closed")
    if any(p.status == PaymentStatus.REFUND_PENDING for p in booking.payments):
        db.rollback()
        raise Conflict("A refund for this booking is already in progress.", code="refund_in_progress")

    captured = _captured_payment(booking)
    refund_id = None
    if refund:
        if captured is None:
            db.rollback()
            raise AppError("There is no captured payment to refund.", code="nothing_to_refund")
        if not captured.razorpay_payment_id:
            db.rollback()
            raise AppError("This payment has no Razorpay payment id; reconcile it first.", code="nothing_to_refund")
        if confirm_refund_paise != captured.amount_paise:
            db.rollback()
            raise AppError("Confirm the refund amount to continue.", code="refund_amount_unconfirmed",
                           details=[{"field": "confirm_refund_paise",
                                     "message": "Must equal the captured amount"}])
        gateway = _require_gateway(gateway)
        payment_repo.lock(db, captured.id)
        # Intent first, in its own commit: survives a crash after Razorpay accepts the refund.
        payment_repo.record_event(db, source="admin", event_type="refund.requested",
                                  order_id=captured.razorpay_order_id, payment_id=captured.razorpay_payment_id,
                                  payload={"amount": captured.amount_paise, "by_admin": actor.id}, result="pending")
        db.commit()
        booking = booking_repo.lock(db, booking_id)
        captured = payment_repo.lock(db, captured.id)
        try:
            res = gateway.refund_payment(str(captured.razorpay_payment_id), captured.amount_paise,
                                         {"booking_reference": booking.reference, "reason": reason[:200]})
        except GatewayError as exc:
            db.rollback()
            audit.record_now(action="payment.refund", outcome="failure", actor=actor, resource_type="booking",
                             resource_id=booking.id, details={"reference": booking.reference,
                                                              "amount_paise": captured.amount_paise}, request=request)
            raise UpstreamError("Razorpay refused the refund. Nothing was changed.", code="refund_failed") from exc
        refund_id = res.get("id")
        move_payment(captured, PaymentStatus.REFUND_PENDING)
        if res.get("status") == "processed":
            move_payment(captured, PaymentStatus.REFUNDED)
            captured.refunded_at = utcnow()
        captured.razorpay_refund_id = refund_id
        payment_repo.record_event(db, source="admin", event_type="refund.created", order_id=captured.razorpay_order_id,
                                  payment_id=captured.razorpay_payment_id,
                                  payload={"refund_id": refund_id, "status": res.get("status")}, result="ok")

    move_booking(booking, BookingStatus.CANCELLED)
    booking.cancelled_at = utcnow()
    booking.cancel_reason = reason[:255]
    booking.hold_expires_at = None
    audit.record(db, action="booking.cancel", actor=actor, resource_type="booking", resource_id=booking.id,
                 details={"reference": booking.reference, "reason": reason[:255], "refund": refund,
                          "refund_id": refund_id, "captured_paise": captured.amount_paise if captured else 0,
                          "paid_but_not_refunded": bool(captured and not refund)}, request=request)
    db.commit()
    db.refresh(booking)
    return booking


def confirm_after_review(db: Session, booking_id: int, note: str, actor: AdminUser,
                         request: Request | None = None) -> Booking:
    """Staff found a room for a guest whose payment arrived after the hold lapsed."""
    booking = booking_repo.lock(db, booking_id)
    if booking.status != BookingStatus.PAYMENT_REVIEW:
        db.rollback()
        raise Conflict("Only bookings awaiting payment review can be confirmed here.", code="not_in_review")
    if _captured_payment(booking) is None:
        db.rollback()
        raise Conflict("This booking has no captured payment.", code="not_paid")
    room = db.execute(select(RoomType).where(RoomType.id == booking.room_type_id).with_for_update()).scalar_one()
    if availability.available_rooms(db, room, booking.check_in, booking.check_out, utcnow(),
                                    exclude_booking_id=booking.id) < 1:
        db.rollback()
        raise Conflict(f"No {room.name} is free for these dates. Increase inventory or refund the guest.",
                       code="sold_out")
    move_booking(booking, BookingStatus.CONFIRMED)
    booking.confirmed_at = utcnow()
    audit.record(db, action="booking.confirm_review", actor=actor, resource_type="booking", resource_id=booking.id,
                 details={"reference": booking.reference, "note": note}, request=request)
    db.commit()
    db.refresh(booking)
    return booking
