"""Razorpay checkout callbacks and webhooks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.rate_limit import enforce
from app.db.session import get_db
from app.models.enums import BookingStatus
from app.schemas.booking import MockCheckoutIn, PaymentClientReport, PaymentResult, PaymentVerify
from app.schemas.common import Message
from app.services import booking_service, notifications, payment_service
from app.services.razorpay_gateway import PaymentGateway, get_gateway

log = logging.getLogger("app.payments")
router = APIRouter(prefix="/payments", tags=["Payments"])

_MESSAGES = {
    BookingStatus.CONFIRMED: "Payment received. Your booking is confirmed.",
    BookingStatus.PENDING_PAYMENT: "Payment received and is being confirmed. This usually takes a few seconds.",
    BookingStatus.PAYMENT_REVIEW: "Payment received. Our reservations team will contact you shortly to "
                                  "finalise your room.",
}


@router.post("/verify", response_model=PaymentResult,
             summary="Verify the signature Razorpay Checkout returned, then confirm the payment with Razorpay")
def verify(data: PaymentVerify, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
           gateway: PaymentGateway | None = Depends(get_gateway)):
    enforce(request, "payment-verify", 30, 600)
    out = payment_service.verify_checkout(db, data, gateway)
    b = out.confirmed_booking
    if out.newly_confirmed:
        notifications.booking_confirmed(background, b)
    if out.needs_review:
        notifications.booking_needs_review(background, b)
    return PaymentResult(booking=booking_service.to_public(b),
                         message=_MESSAGES.get(b.status, "Payment status updated."))


@router.post("/mock/checkout", include_in_schema=False)
def mock_checkout(data: MockCheckoutIn, request: Request, db: Session = Depends(get_db),
                  gateway: PaymentGateway | None = Depends(get_gateway)) -> dict:
    """Test payment mode only (PAYMENT_MODE=mock, never production): 404 otherwise."""
    enforce(request, "payment-mock", 30, 600)
    return payment_service.simulate_mock_payment(db, data.razorpay_order_id, data.outcome, gateway)


@router.post("/report", response_model=Message, status_code=202,
             summary="Record that checkout was closed or failed in the browser (informational only)")
def report(data: PaymentClientReport, request: Request, db: Session = Depends(get_db)):
    enforce(request, "payment-report", 30, 600)
    payment_service.record_client_report(db, data)
    return Message(message="Recorded")


@router.post("/webhook", include_in_schema=True, summary="Razorpay webhook endpoint")
async def webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                  gateway: PaymentGateway | None = Depends(get_gateway),
                  x_razorpay_signature: str = Header(default=""),
                  x_razorpay_event_id: str | None = Header(default=None)):
    # The signature covers the exact bytes Razorpay sent, so read the raw body.
    await run_in_threadpool(enforce, request, "webhook", 600, 60)
    raw = await request.body()
    out = await run_in_threadpool(payment_service.handle_webhook, db, raw, x_razorpay_signature,
                                  x_razorpay_event_id, gateway, request)
    if out.booking is not None:
        if out.newly_confirmed:
            notifications.booking_confirmed(background, out.booking)
        if out.needs_review:
            notifications.booking_needs_review(background, out.booking)
    return {"status": "ok", "result": ",".join(out.notes) or "applied"}
