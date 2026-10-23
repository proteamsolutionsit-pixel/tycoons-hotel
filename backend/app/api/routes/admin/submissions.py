"""Guest submissions from the site's forms: list, update status/notes, CV download."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.errors import NotFound
from app.core.permissions import Permission
from app.core.timeutil import utcnow
from app.db.session import get_db
from app.models import AdminUser, Enquiry, JobApplication, NewsletterSubscriber, SpaAppointment, TableReservation
from app.models.enums import EnquiryKind, SubmissionStatus
from app.schemas.admin import (
    EnquiryOut,
    JobApplicationOut,
    NewsletterOut,
    NewsletterUpdate,
    SpaAppointmentOut,
    SubmissionUpdate,
    TableReservationOut,
)
from app.schemas.common import Page
from app.services import audit, upload_service

router = APIRouter(prefix="/submissions", tags=["Admin: submissions"])
VIEW = require(Permission.SUBMISSIONS_VIEW)
MANAGE = require(Permission.SUBMISSIONS_MANAGE)

SubmissionOut = TableReservationOut | SpaAppointmentOut | EnquiryOut | JobApplicationOut

# kind -> (model, output schema, searchable columns)
KINDS: dict[str, tuple[Any, type[BaseModel], tuple[str, ...]]] = {
    "table-reservations": (TableReservation, TableReservationOut, ("name", "phone")),
    "spa-appointments": (SpaAppointment, SpaAppointmentOut, ("name", "phone")),
    "enquiries": (Enquiry, EnquiryOut, ("name", "email", "company")),
    "applications": (JobApplication, JobApplicationOut, ("name", "email", "position")),
}


def _serialize(kind: str, obj):
    _, schema, _ = KINDS[kind]
    item = schema.model_validate(obj)
    if kind == "spa-appointments":
        return item.model_copy(update={"treatment_name": obj.treatment.form_label if obj.treatment
                                       else "Not sure — advise me"})
    if kind == "applications":
        return item.model_copy(update={"has_cv": bool(obj.cv_path)})
    return item


def _kind(kind: str):
    # 404 (not 422) for an unknown collection, as before the refactor
    if kind not in KINDS:
        raise NotFound("Unknown submission type.")
    return KINDS[kind]


@router.get("/newsletter", response_model=Page[NewsletterOut])
def list_newsletter(active: bool | None = None, q: str | None = Query(None, max_length=100),
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    _: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
    stmt = select(NewsletterSubscriber)
    if active is not None:
        stmt = stmt.where(NewsletterSubscriber.is_active.is_(active))
    if q:
        stmt = stmt.where(NewsletterSubscriber.email.ilike(f"%{q.strip()}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.order_by(NewsletterSubscriber.id.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/newsletter/{sub_id}", response_model=NewsletterOut)
def update_newsletter(sub_id: int, data: NewsletterUpdate, request: Request, actor: AdminUser = Depends(MANAGE),
                      db: Session = Depends(get_db)):
    row = db.get(NewsletterSubscriber, sub_id)
    if row is None:
        raise NotFound("Subscriber not found.")
    row.is_active = data.is_active
    row.unsubscribed_at = None if data.is_active else utcnow()
    audit.record(db, action="newsletter.update", actor=actor, resource_type="newsletter_subscriber",
                 resource_id=row.id, details={"is_active": data.is_active}, request=request)
    db.commit()
    return row


@router.get("/{kind}", response_model=Page[SubmissionOut])
def list_submissions(kind: str, status: SubmissionStatus | None = None,
                     enquiry_kind: EnquiryKind | None = None, q: str | None = Query(None, max_length=100),
                     limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                     _: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
    model, _schema, search_cols = _kind(kind)
    stmt = select(model)
    if status:
        stmt = stmt.where(model.status == status)
    if enquiry_kind and model is Enquiry:
        stmt = stmt.where(Enquiry.kind == enquiry_kind)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(*[getattr(model, c).ilike(like) for c in search_cols]))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(model.id.desc()).limit(limit).offset(offset)).unique().scalars().all()
    return Page(items=[_serialize(kind, r) for r in rows], total=total, limit=limit, offset=offset)


@router.patch("/{kind}/{item_id}", response_model=SubmissionOut)
def update_submission(kind: str, item_id: int, data: SubmissionUpdate, request: Request,
                      actor: AdminUser = Depends(MANAGE), db: Session = Depends(get_db)):
    model, _schema, _cols = _kind(kind)
    obj = db.get(model, item_id)
    if obj is None:
        raise NotFound("Not found.")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(obj, k, v)
    audit.record(db, action="submission.update", actor=actor, resource_type=kind, resource_id=item_id,
                 details={"status": changes["status"].value if changes.get("status") else None,
                          "notes_changed": "staff_notes" in changes}, request=request)
    db.commit()
    db.refresh(obj)
    return _serialize(kind, obj)


@router.get("/applications/{item_id}/cv", summary="Download the applicant's CV")
def download_cv(item_id: int, request: Request, actor: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
    app_row = db.get(JobApplication, item_id)
    path = upload_service.resolve_private(app_row.cv_path) if app_row and app_row.cv_path else None
    if app_row is None or path is None:
        raise NotFound("No CV on file.")
    audit.record(db, action="application.cv_download", actor=actor, resource_type="applications",
                 resource_id=item_id, request=request)
    db.commit()
    return FileResponse(path, media_type=app_row.cv_content_type or "application/octet-stream",
                        filename=app_row.cv_original_name or path.name,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
                                 "Content-Security-Policy": "sandbox"})
