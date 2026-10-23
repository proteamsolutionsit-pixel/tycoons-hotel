from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.timeutil import hotel_today, utcnow
from app.db.session import get_db
from app.models import Booking, Enquiry, JobApplication, Payment, SpaAppointment, TableReservation
from app.models.enums import BookingStatus, PaymentStatus, SubmissionStatus
from app.schemas.admin import Dashboard

router = APIRouter(tags=["Admin: dashboard"])


@router.get("/dashboard", response_model=Dashboard)
def dashboard(_=Depends(get_current_admin), db: Session = Depends(get_db)):
    today = hotel_today()
    now = utcnow()

    def count(stmt) -> int:
        return db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    confirmed = select(Booking.id).where(Booking.status == BookingStatus.CONFIRMED)
    revenue = db.execute(select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
        Payment.status == PaymentStatus.CAPTURED, Payment.captured_at >= now - timedelta(days=30))).scalar_one()
    new = {}
    for key, model in (("table_reservations", TableReservation), ("spa_appointments", SpaAppointment),
                       ("enquiries", Enquiry), ("applications", JobApplication)):
        new[key] = count(select(model.id).where(model.status == SubmissionStatus.NEW))

    return Dashboard(
        arrivals_today=count(confirmed.where(Booking.check_in == today)),
        arrivals_next_7_days=count(confirmed.where(Booking.check_in >= today,
                                                   Booking.check_in < today + timedelta(days=7))),
        in_house_tonight=count(confirmed.where(Booking.check_in <= today, Booking.check_out > today)),
        pending_payment=count(select(Booking.id).where(Booking.status == BookingStatus.PENDING_PAYMENT,
                                                       Booking.hold_expires_at > now)),
        payment_review=count(select(Booking.id).where(Booking.status == BookingStatus.PAYMENT_REVIEW)),
        revenue_30d_paise=int(revenue),
        confirmed_30d=count(confirmed.where(Booking.confirmed_at >= now - timedelta(days=30))),
        new_submissions=new,
    )
