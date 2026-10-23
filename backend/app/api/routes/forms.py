"""The site's request forms: table reservation, spa appointment, business
and contact enquiries, job applications and the newsletter."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.rate_limit import enforce
from app.db.session import get_db
from app.schemas.forms import (
    BusinessEnquiryIn,
    ContactEnquiryIn,
    NewsletterIn,
    SpaAppointmentIn,
    SubmissionAck,
    TableReservationIn,
)
from app.services import forms_service, upload_service

router = APIRouter(tags=["Forms"])

FORM_LIMIT = (8, 600)  # per IP per form: 8 submissions / 10 minutes


@router.post("/dining/reservations", response_model=SubmissionAck, status_code=201,
             summary="Fishy Tales table reservation request")
def table_reservation(data: TableReservationIn, request: Request, background: BackgroundTasks,
                      db: Session = Depends(get_db)):
    enforce(request, "form-dining", *FORM_LIMIT)
    row = forms_service.table_reservation(db, data, background)
    return SubmissionAck(id=row.id, message="Thank you. Our team will call or email to confirm your table.")


@router.post("/spa/appointments", response_model=SubmissionAck, status_code=201,
             summary="Kai Wellness Spa appointment request")
def spa_appointment(data: SpaAppointmentIn, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    enforce(request, "form-spa", *FORM_LIMIT)
    row = forms_service.spa_appointment(db, data, background)
    return SubmissionAck(id=row.id, message="Thank you. Our spa team will confirm your appointment.")


@router.post("/enquiries/business", response_model=SubmissionAck, status_code=201,
             summary="Business Lounge: plan your business stay")
def business_enquiry(data: BusinessEnquiryIn, request: Request, background: BackgroundTasks,
                     db: Session = Depends(get_db)):
    enforce(request, "form-business", *FORM_LIMIT)
    row = forms_service.business_enquiry(db, data, background)
    return SubmissionAck(id=row.id, message="Thank you. Our team will get back to you shortly.")


@router.post("/enquiries/contact", response_model=SubmissionAck, status_code=201, summary="Contact page enquiry")
def contact_enquiry(data: ContactEnquiryIn, request: Request, background: BackgroundTasks,
                    db: Session = Depends(get_db)):
    enforce(request, "form-contact", *FORM_LIMIT)
    row = forms_service.contact_enquiry(db, data, background)
    return SubmissionAck(id=row.id, message="Thank you. We'll be in touch soon.")


@router.post("/careers/applications", response_model=SubmissionAck, status_code=201,
             summary="Job application with optional CV (PDF/DOC/DOCX, max 5 MB)")
async def job_application(request: Request, background: BackgroundTasks,
                          name: str = Form(..., max_length=120), email: str = Form(..., max_length=255),
                          phone: str = Form(..., max_length=32), position: str = Form(..., max_length=120),
                          message: str | None = Form(None, max_length=4000), consent: bool = Form(False),
                          opening_id: int | None = Form(None), cv: UploadFile | None = File(None),
                          db: Session = Depends(get_db)):
    # Database work runs in the threadpool: this handler is async (it streams
    # the upload) and must not block the event loop.
    await run_in_threadpool(enforce, request, "form-careers", 5, 600)
    clean = await run_in_threadpool(forms_service.validate_application, db, name=name, email=email, phone=phone,
                                    position=position, consent=consent, opening_id=opening_id)
    stored = await upload_service.store_cv(cv) if cv is not None and cv.filename else None
    row = await run_in_threadpool(forms_service.save_application, db, clean, message, opening_id, stored, background)
    return SubmissionAck(id=row.id, message="Thank you for applying. Our team will be in touch.")


@router.post("/newsletter", response_model=SubmissionAck, status_code=201, summary="Newsletter sign-up")
def newsletter(data: NewsletterIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "form-newsletter", *FORM_LIMIT)
    forms_service.newsletter(db, data)
    # Same reply (and no row id) whether or not the address was already subscribed.
    return SubmissionAck(id=0, message="Thank you for subscribing.")
