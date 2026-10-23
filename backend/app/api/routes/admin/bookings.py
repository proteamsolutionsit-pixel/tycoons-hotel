from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models import Booking, Payment, PaymentEvent
from app.models.enums import BookingStatus, PaymentStatus
from app.repositories import bookings as booking_repo
from app.schemas.admin import (BookingDetail, BookingRow, CancelIn, PaymentEventOut, PaymentOut, PaymentRow)
from app.schemas.common import Page
from app.services import notifications, payment_service
from app.services.razorpay_gateway import PaymentGateway, get_gateway

router = APIRouter(tags=["Admin: bookings & payments"])


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
                        .order_by(PaymentEvent.id)).scalars().all() if order_ids else []
    return BookingDetail(
        **_row(b), special_requests=b.special_requests, nightly_rate_paise=b.nightly_rate_paise,
        subtotal_paise=b.subtotal_paise, tax_percent=b.tax_percent, tax_paise=b.tax_paise,
        hold_expires_at=b.hold_expires_at, confirmed_at=b.confirmed_at, cancelled_at=b.cancelled_at,
        cancel_reason=b.cancel_reason, payments=[PaymentOut.model_validate(p) for p in b.payments],
        events=[PaymentEventOut.model_validate(e) for e in events],
    )


@router.get("/bookings", response_model=Page[BookingRow])
def list_bookings(status: BookingStatus | None = None, q: str | None = Query(None, max_length=100),
                  check_in_from: date | None = None, check_in_to: date | None = None,
                  limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                  _=Depends(get_current_admin), db: Session = Depends(get_db)):
    stmt = select(Booking)
    if status:
        stmt = stmt.where(Booking.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Booking.reference.ilike(like), Booking.guest_name.ilike(like),
                              Booking.guest_email.ilike(like), Booking.guest_phone.ilike(like)))
    if check_in_from:
        stmt = stmt.where(Booking.check_in >= check_in_from)
    if check_in_to:
        stmt = stmt.where(Booking.check_in <= check_in_to)
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit).offset(offset)
                      ).unique().scalars().all()
    return Page(items=[BookingRow(**_row(b)) for b in rows], total=total, limit=limit, offset=offset)


@router.get("/bookings/{booking_id}", response_model=BookingDetail)
def get_booking(booking_id: int, _=Depends(get_current_admin), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise NotFound("Booking not found.")
    return _detail(db, b)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingDetail,
             summary="Cancel a booking, optionally refunding the captured payment through Razorpay")
def cancel_booking(booking_id: int, data: CancelIn, _=Depends(require_admin), db: Session = Depends(get_db),
                   gateway: PaymentGateway | None = Depends(get_gateway)):
    if db.get(Booking, booking_id) is None:
        raise NotFound("Booking not found.")
    b = payment_service.cancel_booking(db, booking_id, data.reason, data.refund, gateway)
    return _detail(db, b)


@router.post("/payments/{payment_id}/reconcile", response_model=BookingDetail,
             summary="Fetch the order's payments from Razorpay and apply the real outcome")
def reconcile(payment_id: int, background: BackgroundTasks, _=Depends(require_admin), db: Session = Depends(get_db),
              gateway: PaymentGateway | None = Depends(get_gateway)):
    if db.get(Payment, payment_id) is None:
        raise NotFound("Payment not found.")
    out = payment_service.reconcile(db, payment_id, gateway)
    if out.newly_confirmed:
        notifications.booking_confirmed(background, out.booking)
    db.refresh(out.booking)
    return _detail(db, out.booking)


@router.get("/payments", response_model=Page[PaymentRow])
def list_payments(status: PaymentStatus | None = None, q: str | None = Query(None, max_length=100),
                  limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                  _=Depends(get_current_admin), db: Session = Depends(get_db)):
    stmt = select(Payment, Booking.reference, Booking.guest_name).join(Booking, Payment.booking_id == Booking.id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Payment.razorpay_order_id.ilike(like), Payment.razorpay_payment_id.ilike(like),
                              Booking.reference.ilike(like), Booking.guest_name.ilike(like)))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Payment.id.desc()).limit(limit).offset(offset)).all()
    items = [PaymentRow(**PaymentOut.model_validate(p).model_dump(), booking_reference=ref, guest_name=name)
             for p, ref, name in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)
