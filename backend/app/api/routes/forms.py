"""The site's request forms: table reservation, spa appointment, business
and contact enquiries, job applications and the newsletter."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.core.timeutil import hotel_today, utcnow
from app.db.session import get_db
from app.models import (Enquiry, JobApplication, JobOpening, NewsletterSubscriber, SpaAppointment, SpaTreatment,
                        TableReservation)
from app.models.enums import EnquiryKind
from app.schemas.common import Phone, PersonName
from app.schemas.forms import (BusinessEnquiryIn, ContactEnquiryIn, NewsletterIn, SpaAppointmentIn, SubmissionAck,
                               TableReservationIn)
from app.services import notifications, upload_service

router = APIRouter(tags=["Forms"])

FORM_LIMIT = (8, 600)  # per IP per form: 8 submissions / 10 minutes


def _future_date(d, field: str, max_days: int = 365):
    today = hotel_today()
    if d < today:
        raise AppError("Please choose today or a later date.", code="validation_error", status_code=422,
                       details=[{"field": field, "message": "Choose today or a later date"}])
    if d > today + timedelta(days=max_days):
        raise AppError("That date is too far ahead.", code="validation_error", status_code=422,
                       details=[{"field": field, "message": "Choose a date within the next year"}])


@router.post("/dining/reservations", response_model=SubmissionAck, status_code=201,
             summary="Fishy Tales table reservation request")
def table_reservation(data: TableReservationIn, request: Request, background: BackgroundTasks,
                      db: Session = Depends(get_db)):
    enforce(request, "form-dining", *FORM_LIMIT)
    _future_date(data.date, "date", 180)
    row = TableReservation(name=data.name, phone=data.phone, reservation_date=data.date,
                           reservation_time=data.time, party_size=data.guests, occasion=data.occasion,
                           special_requests=data.requests)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Table request #{row.id}: {data.date} {data.time:%H:%M}",
                                      f"{data.name}, {data.phone}\nGuests: {data.guests}\nOccasion: {data.occasion}\n"
                                      f"{data.requests or ''}")
    return SubmissionAck(id=row.id, message="Thank you. Our team will call or email to confirm your table.")


@router.post("/spa/appointments", response_model=SubmissionAck, status_code=201,
             summary="Kai Wellness Spa appointment request")
def spa_appointment(data: SpaAppointmentIn, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    enforce(request, "form-spa", *FORM_LIMIT)
    _future_date(data.date, "date", 180)
    treatment = None
    if data.treatment_id is not None:
        treatment = db.execute(select(SpaTreatment).where(SpaTreatment.id == data.treatment_id,
                                                          SpaTreatment.is_active.is_(True))).scalar_one_or_none()
        if treatment is None:
            raise AppError("Please choose a treatment from the list.", code="validation_error", status_code=422,
                           details=[{"field": "treatment_id", "message": "Unknown treatment"}])
    row = SpaAppointment(name=data.name, phone=data.phone, treatment_id=data.treatment_id,
                         guest_type=data.guest_type, preferred_date=data.date, preferred_time=data.time)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Spa request #{row.id}: {data.date} {data.time:%H:%M}",
                                      f"{data.name}, {data.phone}\n"
                                      f"{treatment.form_label if treatment else 'Not sure - advise me'} "
                                      f"({data.guest_type.value})")
    return SubmissionAck(id=row.id, message="Thank you. Our spa team will confirm your appointment.")


@router.post("/enquiries/business", response_model=SubmissionAck, status_code=201,
             summary="Business Lounge: plan your business stay")
def business_enquiry(data: BusinessEnquiryIn, request: Request, background: BackgroundTasks,
                     db: Session = Depends(get_db)):
    enforce(request, "form-business", *FORM_LIMIT)
    if data.date is not None:
        _future_date(data.date, "date", 730)
    row = Enquiry(kind=EnquiryKind.BUSINESS, company=data.company, name=data.name, email=str(data.email),
                  phone=data.phone, arrival_date=data.date, guests=data.attendees, message=data.requirements,
                  consent=True)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Business enquiry #{row.id}: {data.company}",
                                      f"{data.name} <{data.email}>, {data.phone}\n{data.requirements or ''}")
    return SubmissionAck(id=row.id, message="Thank you. Our team will get back to you shortly.")


@router.post("/enquiries/contact", response_model=SubmissionAck, status_code=201, summary="Contact page enquiry")
def contact_enquiry(data: ContactEnquiryIn, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    enforce(request, "form-contact", *FORM_LIMIT)
    row = Enquiry(kind=EnquiryKind.CONTACT, name=data.name, email=str(data.email), phone=data.phone,
                  topic=data.topic, message=data.message, consent=data.consent)
    db.add(row)
    db.commit()
    notifications.submission_received(background, f"Enquiry #{row.id}: {data.topic}",
                                      f"{data.name} <{data.email}> {data.phone or ''}\n\n{data.message}")
    return SubmissionAck(id=row.id, message="Thank you. We'll be in touch soon.")


_email = TypeAdapter(EmailStr)
_name = TypeAdapter(PersonName)
_phone = TypeAdapter(Phone)


@router.post("/careers/applications", response_model=SubmissionAck, status_code=201,
             summary="Job application with optional CV (PDF/DOC/DOCX, max 5 MB)")
async def job_application(request: Request, background: BackgroundTasks,
                          name: str = Form(..., max_length=120), email: str = Form(..., max_length=255),
                          phone: str = Form(..., max_length=32), position: str = Form(..., max_length=120),
                          message: str | None = Form(None, max_length=4000), consent: bool = Form(False),
                          opening_id: int | None = Form(None), cv: UploadFile | None = File(None),
                          db: Session = Depends(get_db)):
    enforce(request, "form-careers", 5, 600)
    errors = []
    clean: dict = {}
    for field, adapter, value in (("name", _name, name), ("email", _email, email), ("phone", _phone, phone)):
        try:
            clean[field] = adapter.validate_python(value)
        except ValidationError as exc:
            msg = exc.errors()[0]["msg"].removeprefix("Value error, ")
            errors.append({"field": field, "message": msg})
    position = position.strip()
    if len(position) < 2:
        errors.append({"field": "position", "message": "Please tell us which position you are applying for"})
    if not consent:
        errors.append({"field": "consent", "message": "Please agree to your details being used for this application"})
    if opening_id is not None and db.get(JobOpening, opening_id) is None:
        errors.append({"field": "opening_id", "message": "Unknown opening"})
    if errors:
        raise AppError("Please check the highlighted fields.", code="validation_error", status_code=422,
                       details=errors)

    stored = None
    if cv is not None and cv.filename:
        stored = await upload_service.store_cv(cv)
    row = JobApplication(opening_id=opening_id, name=clean["name"], email=str(clean["email"]), phone=clean["phone"],
                         position=position, message=(message or "").strip() or None, consent=True,
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
    notifications.submission_received(background, f"Job application #{row.id}: {position}",
                                      f"{row.name} <{row.email}>, {row.phone}\nCV: {'yes' if stored else 'no'}")
    return SubmissionAck(id=row.id, message="Thank you for applying. Our team will be in touch.")


@router.post("/newsletter", response_model=SubmissionAck, status_code=201, summary="Newsletter sign-up")
def newsletter(data: NewsletterIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "form-newsletter", *FORM_LIMIT)
    email = str(data.email).lower()
    row = db.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)).scalar_one_or_none()
    now = utcnow()
    if row is None:
        row = NewsletterSubscriber(email=email, is_active=True, consent_at=now)
        db.add(row)
    elif not row.is_active:
        row.is_active, row.consent_at, row.unsubscribed_at = True, now, None
    db.commit()
    # Same reply whether or not the address was already subscribed.
    return SubmissionAck(id=row.id, message="Thank you for subscribing.")
