"""Dashboard figures, occupancy calendar and the audit log - all computed
from the database for the signed-in user's permissions; nothing is estimated."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.permissions import Permission
from app.core.timeutil import hotel_today, utcnow
from app.db.session import get_db
from app.models import (
    AdminUser,
    AuditLog,
    Booking,
    Enquiry,
    JobApplication,
    Payment,
    PaymentEvent,
    RoomType,
    SpaAppointment,
    TableReservation,
)
from app.models.enums import BookingStatus, PaymentStatus, SubmissionStatus
from app.schemas.admin import AuditLogOut, Dashboard, Occupancy, OccupancyRoom
from app.schemas.common import Page

router = APIRouter(tags=["Admin: dashboard"])

# Stays that take a room: paid, or paid-awaiting-review
_SOLD = (BookingStatus.CONFIRMED, BookingStatus.PAYMENT_REVIEW)


@router.get("/dashboard", response_model=Dashboard)
def dashboard(_: AdminUser = Depends(require(Permission.DASHBOARD_VIEW)), db: Session = Depends(get_db)):
    today = hotel_today()
    now = utcnow()

    def count(stmt) -> int:
        return db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    confirmed = select(Booking.id).where(Booking.status == BookingStatus.CONFIRMED)
    revenue = db.execute(select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
        Payment.status.in_([PaymentStatus.CAPTURED, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED]),
        Payment.captured_at >= now - timedelta(days=30))).scalar_one()
    refunded = db.execute(select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
        Payment.status == PaymentStatus.REFUNDED, Payment.refunded_at >= now - timedelta(days=30))).scalar_one()
    rooms_total = db.execute(select(func.coalesce(func.sum(RoomType.total_rooms), 0))
                             .where(RoomType.is_active.is_(True))).scalar_one()
    sold_tonight = count(select(Booking.id).where(Booking.status.in_(_SOLD), Booking.check_in <= today,
                                                  Booking.check_out > today))
    new = {}
    for key, model in (("table_reservations", TableReservation), ("spa_appointments", SpaAppointment),
                       ("enquiries", Enquiry), ("applications", JobApplication)):
        new[key] = count(select(model.id).where(model.status == SubmissionStatus.NEW))

    week = now - timedelta(days=7)
    alerts = {
        "payment_review": count(select(Booking.id).where(Booking.status == BookingStatus.PAYMENT_REVIEW)),
        # money authorised but not captured for >30 min: reconcile
        "stuck_authorized": count(select(Payment.id).where(Payment.status == PaymentStatus.AUTHORIZED,
                                                           Payment.updated_at < now - timedelta(minutes=30))),
        "refund_pending": count(select(Payment.id).where(Payment.status == PaymentStatus.REFUND_PENDING)),
        # refunded at Razorpay while the stay is still booked
        "refunded_active_booking": count(select(Booking.id).join(Payment, Payment.booking_id == Booking.id).where(
            Booking.status.in_(_SOLD), Payment.status == PaymentStatus.REFUNDED)),
        "payment_mismatch_7d": count(select(PaymentEvent.id).where(
            PaymentEvent.created_at >= week, or_(PaymentEvent.result.like("%mismatch%"),
                                                 PaymentEvent.result.like("%unknown_order%")))),
        "webhook_signature_failures_7d": count(select(AuditLog.id).where(
            AuditLog.occurred_at >= week, AuditLog.action == "security.webhook_signature_rejected")),
        "failed_logins_24h": count(select(AuditLog.id).where(
            AuditLog.occurred_at >= now - timedelta(hours=24), AuditLog.action == "auth.login_failed")),
    }

    return Dashboard(
        arrivals_today=count(confirmed.where(Booking.check_in == today)),
        departures_today=count(confirmed.where(Booking.check_out == today)),
        arrivals_next_7_days=count(confirmed.where(Booking.check_in >= today,
                                                   Booking.check_in < today + timedelta(days=7))),
        in_house_tonight=count(confirmed.where(Booking.check_in <= today, Booking.check_out > today)),
        rooms_total=int(rooms_total), rooms_sold_tonight=sold_tonight,
        occupancy_tonight_pct=round(100 * sold_tonight / rooms_total, 1) if rooms_total else 0.0,
        pending_payment=count(select(Booking.id).where(Booking.status == BookingStatus.PENDING_PAYMENT,
                                                       Booking.hold_expires_at > now)),
        payment_review=alerts["payment_review"],
        revenue_30d_paise=int(revenue), refunded_30d_paise=int(refunded),
        confirmed_30d=count(confirmed.where(Booking.confirmed_at >= now - timedelta(days=30))),
        new_submissions=new, alerts=alerts,
    )


@router.get("/occupancy", response_model=Occupancy, summary="Rooms sold and held per room type per night")
def occupancy(start: date | None = None, days: int = Query(14, ge=1, le=62),
              _: AdminUser = Depends(require(Permission.BOOKINGS_VIEW)), db: Session = Depends(get_db)):
    start = start or hotel_today()
    end = start + timedelta(days=days)
    now = utcnow()
    rooms = db.execute(select(RoomType).order_by(RoomType.sort_order, RoomType.id)).scalars().all()
    stays = db.execute(select(Booking.room_type_id, Booking.check_in, Booking.check_out, Booking.status).where(
        Booking.check_in < end, Booking.check_out > start,
        or_(Booking.status.in_(_SOLD),
            and_(Booking.status == BookingStatus.PENDING_PAYMENT, Booking.hold_expires_at > now)))).all()
    nights = [start + timedelta(days=i) for i in range(days)]
    out = []
    for r in rooms:
        booked, held = [0] * days, [0] * days
        for rid, ci, co, st in stays:
            if rid != r.id:
                continue
            for i, n in enumerate(nights):
                if ci <= n < co:
                    (held if st == BookingStatus.PENDING_PAYMENT else booked)[i] += 1
        out.append(OccupancyRoom(slug=r.slug, name=r.name, total_rooms=r.total_rooms, booked=booked, held=held))
    return Occupancy(start=start, days=nights, rooms=out)


@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="Audit trail (read-only)")
def audit_logs(action: str | None = Query(None, max_length=64), actor_id: int | None = None,
               resource_type: str | None = Query(None, max_length=40), resource_id: str | None = Query(None, max_length=64),
               outcome: str | None = Query(None, pattern="^(success|failure|denied)$"),
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               _: AdminUser = Depends(require(Permission.AUDIT_VIEW)), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action.strip()}%"))
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=items, total=total, limit=limit, offset=offset)
