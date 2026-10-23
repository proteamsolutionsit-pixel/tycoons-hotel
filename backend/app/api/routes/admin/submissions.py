"""Guest submissions from the site's forms: list, update status/notes, CV download."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models import Enquiry, JobApplication, NewsletterSubscriber, SpaAppointment, TableReservation
from app.models.enums import EnquiryKind, SubmissionStatus
from app.core.timeutil import utcnow
from app.schemas.admin import (EnquiryOut, JobApplicationOut, NewsletterOut, NewsletterUpdate, SpaAppointmentOut,
                               SubmissionUpdate, TableReservationOut)
from app.schemas.common import Page
from app.services import upload_service

router = APIRouter(prefix="/submissions", tags=["Admin: submissions"])

# kind -> (model, output schema, searchable columns)
KINDS = {
    "table-reservations": (TableReservation, TableReservationOut, ("name", "phone")),
    "spa-appointments": (SpaAppointment, SpaAppointmentOut, ("name", "phone")),
    "enquiries": (Enquiry, EnquiryOut, ("name", "email", "company")),
    "applications": (JobApplication, JobApplicationOut, ("name", "email", "position")),
}


def _serialize(kind: str, obj):
    _, schema, _ = KINDS[kind]
    item = schema.model_validate(obj)
    if kind == "spa-appointments":
        item.treatment_name = obj.treatment.form_label if obj.treatment else "Not sure — advise me"
    if kind == "applications":
        item.has_cv = bool(obj.cv_path)
    return item


def _kind(kind: str):
    if kind not in KINDS:
        raise NotFound("Unknown submission type.")
    return KINDS[kind]


@router.get("/newsletter", response_model=Page[NewsletterOut])
def list_newsletter(active: bool | None = None, q: str | None = Query(None, max_length=100),
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    _=Depends(get_current_admin), db: Session = Depends(get_db)):
    stmt = select(NewsletterSubscriber)
    if active is not None:
        stmt = stmt.where(NewsletterSubscriber.is_active.is_(active))
    if q:
        stmt = stmt.where(NewsletterSubscriber.email.ilike(f"%{q.strip()}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.order_by(NewsletterSubscriber.id.desc()).limit(limit).offset(offset)).scalars().all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/newsletter/{sub_id}", response_model=NewsletterOut)
def update_newsletter(sub_id: int, data: NewsletterUpdate, _=Depends(get_current_admin),
                      db: Session = Depends(get_db)):
    row = db.get(NewsletterSubscriber, sub_id)
    if row is None:
        raise NotFound("Subscriber not found.")
    row.is_active = data.is_active
    row.unsubscribed_at = None if data.is_active else utcnow()
    db.commit()
    return row


@router.get("/{kind}")
def list_submissions(kind: str, status: SubmissionStatus | None = None,
                     enquiry_kind: EnquiryKind | None = None, q: str | None = Query(None, max_length=100),
                     limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                     _=Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
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
    return {"items": [_serialize(kind, r).model_dump(mode="json") for r in rows], "total": total,
            "limit": limit, "offset": offset}


@router.patch("/{kind}/{item_id}")
def update_submission(kind: str, item_id: int, data: SubmissionUpdate, _=Depends(get_current_admin),
                      db: Session = Depends(get_db)) -> dict:
    model, _schema, _cols = _kind(kind)
    obj = db.get(model, item_id)
    if obj is None:
        raise NotFound("Not found.")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _serialize(kind, obj).model_dump(mode="json")


@router.get("/applications/{item_id}/cv", summary="Download the applicant's CV")
def download_cv(item_id: int, _=Depends(get_current_admin), db: Session = Depends(get_db)):
    app_row = db.get(JobApplication, item_id)
    path = upload_service.resolve_private(app_row.cv_path) if app_row and app_row.cv_path else None
    if path is None:
        raise NotFound("No CV on file.")
    return FileResponse(path, media_type=app_row.cv_content_type or "application/octet-stream",
                        filename=app_row.cv_original_name or path.name,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
                                 "Content-Security-Policy": "sandbox"})
