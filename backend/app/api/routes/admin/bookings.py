from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require
from app.api.tabular import EXPORT_MAX_ROWS, csv_response, like_pattern, ordered, record_export
from app.core.errors import Forbidden, NotFound
from app.core.permissions import Permission, user_can
from app.db.session import get_db
from app.models import AdminUser, Booking, Payment, PaymentEvent
from app.models.enums import BookingStatus, PaymentStatus
from app.repositories import bookings as booking_repo
from app.schemas.admin import (
    BookingDetail,
    BookingRow,
    CancelIn,
    ConfirmReviewIn,
    PaymentEventOut,
    PaymentOut,
    PaymentRow,
)
from app.schemas.common import Page
from app.services import audit, notifications, payment_service
from app.services.razorpay_gateway import PaymentGateway, get_gateway

router = APIRouter(tags=["Admin: bookings & payments"])

BookingSort = Literal["created_at", "check_in", "check_out", "total", "guest", "reference", "status"]
PaymentSort = Literal["created_at", "amount", "status", "captured_at", "reference", "guest"]

_BOOKING_SORT = {"created_at": Booking.created_at, "check_in": Booking.check_in, "check_out": Booking.check_out,
                 "total": Booking.total_paise, "guest": Booking.guest_name, "reference": Booking.reference,
                 "status": Booking.status}
_PAYMENT_SORT = {"created_at": Payment.created_at, "amount": Payment.amount_paise, "status": Payment.status,
                 "captured_at": Payment.captured_at, "reference": Booking.reference, "guest": Booking.guest_name}


def _row(b: Booking) -> dict:
    p = booking_repo.latest_payment(b)
    return dict(id=b.id, reference=b.reference, status=b.status, room_type_name=b.room_type.name,
                check_in=b.check_in, check_out=b.check_out, nights=b.nights, adults=b.adults, children=b.children,
                guest_name=b.guest_name, guest_email=b.guest_email, guest_phone=b.guest_phone,
                total_paise=b.total_paise, currency=b.currency, payment_status=p.status if p else None,
                created_at=b.created_at)


def _detail(db: Session, b: Booking) -> BookingDetail:
    order_ids = [p.razorpay_order_id for p in b.payments]
    events = db.execute(select(PaymentEvent).where(PaymentEvent.razorpay_order_id.in_(order_ids))
                        .order_by(PaymentEvent.id).limit(200)).scalars().all() if order_ids else []
    return BookingDetail(
        **_row(b), special_requests=b.special_requests, nightly_rate_paise=b.nightly_rate_paise,
        subtotal_paise=b.subtotal_paise, tax_percent=b.tax_percent, tax_paise=b.tax_paise,
        hold_expires_at=b.hold_expires_at, confirmed_at=b.confirmed_at, cancelled_at=b.cancelled_at,
        cancel_reason=b.cancel_reason, terms_version=b.terms_version, terms_accepted_at=b.terms_accepted_at,
        cancellation_policy=b.cancellation_policy,
        payments=[PaymentOut.model_validate(p) for p in b.payments],
        events=[PaymentEventOut.model_validate(e) for e in events],
    )


def _get(db: Session, booking_id: int) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None:
        raise NotFound("Booking not found.")
    return b


def _booking_filters(status: BookingStatus | None = None, q: str | None = Query(None, max_length=100),
                     check_in_from: date | None = None, check_in_to: date | None = None,
                     sort: BookingSort = "created_at", order: Literal["asc", "desc"] = "desc") -> dict:
    return dict(status=status, q=q, check_in_from=check_in_from, check_in_to=check_in_to, sort=sort, order=order)


def _booking_query(*, status, q, check_in_from, check_in_to, sort, order):
    stmt = select(Booking)
    if status:
        stmt = stmt.where(Booking.status == status)
    if q:
        like = like_pattern(q)
        stmt = stmt.where(or_(Booking.reference.like(like), Booking.guest_name.like(like),
                              Booking.guest_email.like(like), Booking.guest_phone.like(like)))
    if check_in_from:
        stmt = stmt.where(Booking.check_in >= check_in_from)
    if check_in_to:
        stmt = stmt.where(Booking.check_in <= check_in_to)
    return stmt, ordered(stmt, _BOOKING_SORT[sort], order, Booking.id)


@router.get("/bookings", response_model=Page[BookingRow])
def list_bookings(filters: dict = Depends(_booking_filters),
                  limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0),
                  _: AdminUser = Depends(require(Permission.BOOKINGS_VIEW)), db: Session = Depends(get_db)):
    stmt, sorted_stmt = _booking_query(**filters)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(sorted_stmt.options(selectinload(Booking.payments))   # no per-row payment query
                      .limit(limit).offset(offset)).unique().scalars().all()
    return Page(items=[BookingRow(**_row(b)) for b in rows], total=total, limit=limit, offset=offset)


# Declared before /bookings/{booking_id} so "export" is not read as an id
@router.get("/bookings/export", summary="Download the filtered bookings as CSV (up to 10,000 rows)")
def export_bookings(request: Request, filters: dict = Depends(_booking_filters),
                    actor: AdminUser = Depends(require(Permission.DATA_EXPORT)), db: Session = Depends(get_db)):
    _, sorted_stmt = _booking_query(**filters)
    rows = db.execute(sorted_stmt.options(selectinload(Booking.payments)).limit(EXPORT_MAX_ROWS)).unique().scalars().all()
    record_export(request, actor, "booking", len(rows), filters)
    header = ["reference", "status", "room", "check_in", "check_out", "nights", "adults", "children", "guest_name",
              "guest_email", "guest_phone", "total_inr", "payment_status", "created_at_utc"]
    out = []
    for b in rows:
        r = _row(b)
        out.append([r["reference"], r["status"], r["room_type_name"], r["check_in"], r["check_out"], r["nights"],
                    r["adults"], r["children"], r["guest_name"], r["guest_email"], r["guest_phone"],
                    f"{r['total_paise'] / 100:.2f}", r["payment_status"], r["created_at"]])
    return csv_response("bookings", header, out)


@router.get("/bookings/{booking_id}", response_model=BookingDetail)
def get_booking(booking_id: int, _: AdminUser = Depends(require(Permission.BOOKINGS_VIEW)),
                db: Session = Depends(get_db)):
    return _detail(db, _get(db, booking_id))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingDetail,
             summary="Cancel a booking; with refund=true also refunds the captured payment through Razorpay")
def cancel_booking(booking_id: int, data: CancelIn, request: Request,
                   actor: AdminUser = Depends(require(Permission.BOOKINGS_MANAGE)), db: Session = Depends(get_db),
                   gateway: PaymentGateway | None = Depends(get_gateway)):
    _get(db, booking_id)
    if data.refund and not user_can(actor, Permission.PAYMENTS_REFUND):
        audit.record_now(action="security.permission_denied", outcome="denied", actor=actor,
                         details={"permission": Permission.PAYMENTS_REFUND.value, "booking_id": booking_id},
                         request=request)
        raise Forbidden("You don't have permission to issue refunds.", code="permission_denied")
    b = payment_service.cancel_booking(db, booking_id, reason=data.reason, refund=data.refund,
                                       confirm_refund_paise=data.confirm_refund_paise, gateway=gateway,
                                       actor=actor, request=request)
    return _detail(db, b)


@router.post("/bookings/{booking_id}/confirm", response_model=BookingDetail,
             summary="Confirm a payment-review booking once a room has been found")
def confirm_review(booking_id: int, data: ConfirmReviewIn, request: Request, background: BackgroundTasks,
                   actor: AdminUser = Depends(require(Permission.BOOKINGS_MANAGE)), db: Session = Depends(get_db)):
    _get(db, booking_id)
    b = payment_service.confirm_after_review(db, booking_id, data.note, actor, request)
    notifications.booking_confirmed(background, b)
    return _detail(db, b)


@router.post("/payments/{payment_id}/reconcile", response_model=BookingDetail,
             summary="Fetch the order's payments from Razorpay and apply the real outcome")
def reconcile(payment_id: int, request: Request, background: BackgroundTasks,
              actor: AdminUser = Depends(require(Permission.PAYMENTS_RECONCILE)), db: Session = Depends(get_db),
              gateway: PaymentGateway | None = Depends(get_gateway)):
    if db.get(Payment, payment_id) is None:
        raise NotFound("Payment not found.")
    out = payment_service.reconcile(db, payment_id, gateway, actor=actor, request=request)
    b = out.confirmed_booking
    if out.newly_confirmed:
        notifications.booking_confirmed(background, b)
    db.refresh(b)
    return _detail(db, b)


def _payment_filters(status: PaymentStatus | None = None, q: str | None = Query(None, max_length=100),
                     sort: PaymentSort = "created_at", order: Literal["asc", "desc"] = "desc") -> dict:
    return dict(status=status, q=q, sort=sort, order=order)


def _payment_query(*, status, q, sort, order):
    stmt = select(Payment, Booking.reference, Booking.guest_name).join(Booking, Payment.booking_id == Booking.id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if q:
        like = like_pattern(q)
        stmt = stmt.where(or_(Payment.razorpay_order_id.like(like), Payment.razorpay_payment_id.like(like),
                              Payment.razorpay_refund_id.like(like), Booking.reference.like(like),
                              Booking.guest_name.like(like)))
    return stmt, ordered(stmt, _PAYMENT_SORT[sort], order, Payment.id)


@router.get("/payments", response_model=Page[PaymentRow])
def list_payments(filters: dict = Depends(_payment_filters),
                  limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0),
                  _: AdminUser = Depends(require(Permission.PAYMENTS_VIEW)), db: Session = Depends(get_db)):
    stmt, sorted_stmt = _payment_query(**filters)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(sorted_stmt.limit(limit).offset(offset)).all()
    items = [PaymentRow(**PaymentOut.model_validate(p).model_dump(), booking_reference=ref, guest_name=name)
             for p, ref, name in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/payments/export", summary="Download the filtered payments as CSV (up to 10,000 rows)")
def export_payments(request: Request, filters: dict = Depends(_payment_filters),
                    actor: AdminUser = Depends(require(Permission.DATA_EXPORT)), db: Session = Depends(get_db)):
    _, sorted_stmt = _payment_query(**filters)
    rows = db.execute(sorted_stmt.limit(EXPORT_MAX_ROWS)).all()
    record_export(request, actor, "payment", len(rows), filters)
    header = ["booking_reference", "guest_name", "razorpay_order_id", "razorpay_payment_id", "razorpay_refund_id",
              "amount_inr", "currency", "status", "method", "captured_at_utc", "refunded_at_utc", "created_at_utc"]
    return csv_response("payments", header, (
        [ref, name, p.razorpay_order_id, p.razorpay_payment_id, p.razorpay_refund_id, f"{p.amount_paise / 100:.2f}",
         p.currency, p.status, p.method, p.captured_at, p.refunded_at, p.created_at] for p, ref, name in rows))
