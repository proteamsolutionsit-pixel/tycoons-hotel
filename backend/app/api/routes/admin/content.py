"""Rooms & rates, spa treatments, content cards, gallery, job openings,
site settings and image uploads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_admin
from app.api.routes.admin.crud import crud_router
from app.core.errors import AppError, NotFound
from app.db.session import get_db
from app.models import ContentCard, GalleryImage, JobOpening, RoomType, SiteSetting, SpaTreatment
from app.repositories import settings as settings_repo
from app.schemas.admin import (ContentCardCreate, ContentCardOut, ContentCardUpdate, GalleryImageCreate,
                               GalleryImageOut, GalleryImageUpdate, JobOpeningCreate, JobOpeningOut,
                               JobOpeningUpdate, RoomTypeCreate, RoomTypeOut, RoomTypeUpdate, SettingOut,
                               SettingUpdate, SpaTreatmentCreate, SpaTreatmentOut, SpaTreatmentUpdate, UploadOut)
from app.services import upload_service

router = APIRouter()

router.include_router(crud_router(
    prefix="/room-types", tag="Admin: rooms & rates", model=RoomType, out=RoomTypeOut, create=RoomTypeCreate,
    update=RoomTypeUpdate, order_by=(RoomType.sort_order, RoomType.id),
    delete_hint="This room type has bookings and can't be deleted. Set it inactive instead."))
router.include_router(crud_router(
    prefix="/spa-treatments", tag="Admin: content", model=SpaTreatment, out=SpaTreatmentOut,
    create=SpaTreatmentCreate, update=SpaTreatmentUpdate, order_by=(SpaTreatment.sort_order, SpaTreatment.id)))
router.include_router(crud_router(
    prefix="/content-cards", tag="Admin: content", model=ContentCard, out=ContentCardOut, create=ContentCardCreate,
    update=ContentCardUpdate, order_by=(ContentCard.section, ContentCard.sort_order, ContentCard.id),
    filters={"section": ContentCard.section}))
router.include_router(crud_router(
    prefix="/gallery", tag="Admin: content", model=GalleryImage, out=GalleryImageOut, create=GalleryImageCreate,
    update=GalleryImageUpdate, order_by=(GalleryImage.sort_order, GalleryImage.id),
    filters={"category": GalleryImage.category}))
router.include_router(crud_router(
    prefix="/job-openings", tag="Admin: content", model=JobOpening, out=JobOpeningOut, create=JobOpeningCreate,
    update=JobOpeningUpdate, order_by=(JobOpening.sort_order, JobOpening.id)))


@router.get("/settings", response_model=list[SettingOut], tags=["Admin: settings"])
def list_settings(_=Depends(get_current_admin), db: Session = Depends(get_db)):
    return settings_repo.all_settings(db)


@router.put("/settings/{key}", response_model=SettingOut, tags=["Admin: settings"])
def update_setting(key: str, data: SettingUpdate, _=Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(SiteSetting, key)
    if row is None:
        raise NotFound("Unknown setting.")
    _validate_setting(row, data.value)
    row.value = data.value
    db.commit()
    db.refresh(row)
    return row


def _validate_setting(row: SiteSetting, value) -> None:
    """Keep each setting the same shape as its seeded value, so the site never
    receives something it can't render."""
    current = row.value

    def bad(msg: str):
        raise AppError(msg, code="validation_error", status_code=422, details=[{"field": "value", "message": msg}])

    if row.key == "room_tax_percent":
        if not isinstance(value, (int, float)) or not 0 <= value <= 100:
            bad("Enter a percentage between 0 and 100.")
        return
    if isinstance(current, str):
        if not isinstance(value, str) or len(value) > 500:
            bad("Enter text (up to 500 characters).")
    elif isinstance(current, list):
        if not isinstance(value, list) or len(value) > 30:
            bad("Enter a list (up to 30 items).")
        if current and isinstance(current[0], dict):
            for item in value:
                if not (isinstance(item, dict) and isinstance(item.get("label"), str)
                        and isinstance(item.get("value"), str)):
                    bad("Each row needs a label and a value.")
        elif not all(isinstance(v, str) and len(v) <= 200 for v in value):
            bad("Each item must be text (up to 200 characters).")
    if row.key.endswith("_url") and isinstance(value, str) and value and not value.startswith(("https://", "/")):
        bad("Links must start with https:// or /.")


@router.post("/uploads/image", response_model=UploadOut, tags=["Admin: content"],
             summary="Upload a JPG/PNG/WebP image; returns the URL to use in content")
async def upload_image(file: UploadFile = File(...), _=Depends(require_admin)):
    stored, url = await upload_service.store_image(file)
    return UploadOut(url=url, size=stored.size)
