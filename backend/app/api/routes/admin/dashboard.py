"""Dashboard figures, occupancy calendar and the audit log - all computed
from the database for the signed-in user's permissions; nothing is estimated."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.api.tabular import EXPORT_MAX_ROWS, csv_response, like_pattern, ordered, record_export
from app.core.permissions import Permission
from app.core.timeutil import hotel_day_start_utc, hotel_today, utcnow
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


AuditSort = Literal["occurred_at", "actor", "action", "resource", "outcome", "ip"]
_AUDIT_SORT = {"occurred_at": AuditLog.id, "actor": AuditLog.actor_email, "action": AuditLog.action,
               "resource": AuditLog.resource_type, "outcome": AuditLog.outcome, "ip": AuditLog.ip}


def _audit_query(*, q: str | None, action: str | None, actor_id: int | None, resource_type: str | None,
                 resource_id: str | None, outcome: str | None, date_from: date | None, date_to: date | None,
                 sort: str, order: str):
    stmt = select(AuditLog)
    if q:
        like = like_pattern(q)
        stmt = stmt.where(or_(AuditLog.actor_email.like(like), AuditLog.action.like(like),
                              AuditLog.resource_type.like(like), AuditLog.resource_id.like(like),
                              AuditLog.ip.like(like), AuditLog.request_id.like(like)))
    if action:
        stmt = stmt.where(AuditLog.action.like(like_pattern(action, prefix=True)))
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    # Dates are the hotel's calendar days; occurred_at is naive UTC
    if date_from:
        stmt = stmt.where(AuditLog.occurred_at >= hotel_day_start_utc(date_from))
    if date_to:
        stmt = stmt.where(AuditLog.occurred_at < hotel_day_start_utc(date_to + timedelta(days=1)))
    return stmt, ordered(stmt, _AUDIT_SORT[sort], order, AuditLog.id)


def _audit_filters(q: str | None = Query(None, max_length=100, description="Search actor, action, resource, IP, request id"),
                   action: str | None = Query(None, max_length=64, description="Action starts with"),
                   actor_id: int | None = None,
                   resource_type: str | None = Query(None, max_length=40), resource_id: str | None = Query(None, max_length=64),
                   outcome: str | None = Query(None, pattern="^(success|failure|denied)$"),
                   date_from: date | None = None, date_to: date | None = None,
                   sort: AuditSort = "occurred_at", order: Literal["asc", "desc"] = "desc") -> dict:
    return dict(q=q, action=action, actor_id=actor_id, resource_type=resource_type, resource_id=resource_id,
                outcome=outcome, date_from=date_from, date_to=date_to, sort=sort, order=order)


@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="Audit trail (read-only)")
def audit_logs(filters: dict = Depends(_audit_filters), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               _: AdminUser = Depends(require(Permission.AUDIT_VIEW)), db: Session = Depends(get_db)):
    stmt, sorted_stmt = _audit_query(**filters)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(sorted_stmt.limit(limit).offset(offset)).scalars().all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/audit-logs/export", summary="Download the filtered audit trail as CSV (up to 10,000 rows)")
def export_audit_logs(request: Request, filters: dict = Depends(_audit_filters),
                      actor: AdminUser = Depends(require(Permission.AUDIT_VIEW)), db: Session = Depends(get_db)):
    _, sorted_stmt = _audit_query(**filters)
    rows = db.execute(sorted_stmt.limit(EXPORT_MAX_ROWS)).scalars().all()
    record_export(request, actor, "audit", len(rows), filters)
    return csv_response("audit-log", ["id", "occurred_at_utc", "actor_type", "actor_id", "actor_email", "action",
                                      "resource_type", "resource_id", "outcome", "ip", "request_id", "details"],
                        ((e.id, e.occurred_at, e.actor_type, e.actor_id, e.actor_email, e.action, e.resource_type,
                          e.resource_id, e.outcome, e.ip, e.request_id, e.details) for e in rows))
