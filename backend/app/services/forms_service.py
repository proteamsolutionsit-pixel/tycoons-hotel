"""Business rules and persistence for the site's request forms."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import BackgroundTasks
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.timeutil import hotel_today, utcnow
from app.models import (
    Enquiry,
    JobApplication,
    JobOpening,
    NewsletterSubscriber,
    SpaAppointment,
    SpaTreatment,
    TableReservation,
)
from app.models.enums import EnquiryKind
from app.schemas.common import PersonName, Phone
from app.schemas.forms import BusinessEnquiryIn, ContactEnquiryIn, NewsletterIn, SpaAppointmentIn, TableReservationIn
from app.services import notifications, upload_service
from app.services.upload_service import StoredFile


def _invalid(field: str, message: str, summary: str = "Please check the highlighted fields.") -> AppError:
    return AppError(summary, code="validation_error", status_code=422, details=[{"field": field, "message": message}])


def require_future_date(d: date, field: str, max_days: int = 365) -> None:
    today = hotel_today()
    if d < today:
        raise _invalid(field, "Choose today or a later date", "Please choose today or a later date.")
    if d > today + timedelta(days=max_days):
        raise _invalid(field, "Choose a date within the next year", "That date is too far ahead.")


def table_reservation(db: Session, data: TableReservationIn, background: BackgroundTasks) -> TableReservation:
    require_future_date(data.date, "date", 180)
    row = TableReservation(name=data.name, phone=data.phone, reservation_date=data.date,
                           reservation_time=data.time, party_size=data.guests, occasion=data.occasion,
                           special_requests=data.requests)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Table request #{row.id}: {data.date} {data.time:%H:%M}",
                                      f"{data.name}, {data.phone}\nGuests: {data.guests}\nOccasion: {data.occasion}\n"
                                      f"{data.requests or ''}")
    return row


def spa_appointment(db: Session, data: SpaAppointmentIn, background: BackgroundTasks) -> SpaAppointment:
    require_future_date(data.date, "date", 180)
    treatment = None
    if data.treatment_id is not None:
        treatment = db.execute(select(SpaTreatment).where(SpaTreatment.id == data.treatment_id,
                                                          SpaTreatment.is_active.is_(True))).scalar_one_or_none()
        if treatment is None:
            raise _invalid("treatment_id", "Unknown treatment", "Please choose a treatment from the list.")
    row = SpaAppointment(name=data.name, phone=data.phone, treatment_id=data.treatment_id,
                         guest_type=data.guest_type, preferred_date=data.date, preferred_time=data.time)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Spa request #{row.id}: {data.date} {data.time:%H:%M}",
                                      f"{data.name}, {data.phone}\n"
                                      f"{treatment.form_label if treatment else 'Not sure - advise me'} "
                                      f"({data.guest_type.value})")
    return row


def business_enquiry(db: Session, data: BusinessEnquiryIn, background: BackgroundTasks) -> Enquiry:
    if data.date is not None:
        require_future_date(data.date, "date", 730)
    row = Enquiry(kind=EnquiryKind.BUSINESS, company=data.company, name=data.name, email=str(data.email),
                  phone=data.phone, arrival_date=data.date, guests=data.attendees, message=data.requirements,
                  consent=True)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Business enquiry #{row.id}: {data.company}",
                                      f"{data.name} <{data.email}>, {data.phone}\n{data.requirements or ''}")
    return row


def contact_enquiry(db: Session, data: ContactEnquiryIn, background: BackgroundTasks) -> Enquiry:
    row = Enquiry(kind=EnquiryKind.CONTACT, name=data.name, email=str(data.email), phone=data.phone,
                  topic=data.topic, message=data.message, consent=data.consent)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Enquiry #{row.id}: {data.topic}",
                                      f"{data.name} <{data.email}> {data.phone or ''}\n\n{data.message}")
    return row


def newsletter(db: Session, data: NewsletterIn) -> NewsletterSubscriber:
    email = str(data.email).lower()
    row = db.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)).scalar_one_or_none()
    now = utcnow()
    if row is None:
        row = NewsletterSubscriber(email=email, is_active=True, consent_at=now)
        db.add(row)
    elif not row.is_active:
        row.is_active, row.consent_at, row.unsubscribed_at = True, now, None
    db.commit()
    return row


# -- Job applications (multipart, so fields arrive as plain strings) ---------

_email: TypeAdapter[str] = TypeAdapter(EmailStr)
_name: TypeAdapter[str] = TypeAdapter(PersonName)
_phone: TypeAdapter[str] = TypeAdapter(Phone)


def validate_application(db: Session, *, name: str, email: str, phone: str, position: str, consent: bool,
                         opening_id: int | None) -> dict:
    errors, clean = [], {}
    for field, adapter, value in (("name", _name, name), ("email", _email, email), ("phone", _phone, phone)):
        try:
            clean[field] = adapter.validate_python(value)
        except ValidationError as exc:
            errors.append({"field": field, "message": exc.errors()[0]["msg"].removeprefix("Value error, ")})
    clean["position"] = position.strip()
    if len(clean["position"]) < 2:
        errors.append({"field": "position", "message": "Please tell us which position you are applying for"})
    if not consent:
        errors.append({"field": "consent", "message": "Please agree to your details being used for this application"})
    if opening_id is not None and db.get(JobOpening, opening_id) is None:
        errors.append({"field": "opening_id", "message": "Unknown opening"})
    if errors:
        raise AppError("Please check the highlighted fields.", code="validation_error", status_code=422,
                       details=errors)
    return clean


def save_application(db: Session, clean: dict, message: str | None, opening_id: int | None,
                     stored: StoredFile | None, background: BackgroundTasks) -> JobApplication:
    row = JobApplication(opening_id=opening_id, name=clean["name"], email=str(clean["email"]), phone=clean["phone"],
                         position=clean["position"], message=(message or "").strip() or None, consent=True,
                         cv_path=stored.relative_path if stored else None,
                         cv_original_name=stored.original_name if stored else None,
                         cv_content_type=stored.content_type if stored else None,
                         cv_size=stored.size if stored else None)
    try:
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        if stored:
            upload_service.delete_private(stored.relative_path)
        raise
    notifications.submission_received(background, f"Job application #{row.id}: {row.position}",
                                      f"{row.name} <{row.email}>, {row.phone}\nCV: {'yes' if stored else 'no'}")
    return row
