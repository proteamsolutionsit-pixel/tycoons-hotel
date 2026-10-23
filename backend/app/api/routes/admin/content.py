"""Rooms & rates, spa treatments, content cards, gallery, job openings,
site settings and image uploads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import require
from app.api.routes.admin.crud import crud_router
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import AdminUser, ContentCard, GalleryImage, JobOpening, RoomType, SpaTreatment
from app.repositories import settings as settings_repo
from app.schemas.admin import (
    ContentCardCreate,
    ContentCardOut,
    ContentCardUpdate,
    GalleryImageCreate,
    GalleryImageOut,
    GalleryImageUpdate,
    JobOpeningCreate,
    JobOpeningOut,
    JobOpeningUpdate,
    RoomTypeCreate,
    RoomTypeOut,
    RoomTypeUpdate,
    SettingOut,
    SettingUpdate,
    SpaTreatmentCreate,
    SpaTreatmentOut,
    SpaTreatmentUpdate,
    UploadOut,
)
from app.services import audit, settings_service, upload_service

router = APIRouter()
_VIEW, _CONTENT = Permission.CATALOG_VIEW, Permission.CONTENT_MANAGE

router.include_router(crud_router(
    prefix="/room-types", tag="Admin: rooms & rates", model=RoomType, out=RoomTypeOut, create=RoomTypeCreate,
    update=RoomTypeUpdate, order_by=(RoomType.sort_order, RoomType.id), resource="room_type",
    view=_VIEW, manage=Permission.CATALOG_MANAGE,
    delete_hint="This room type has bookings and can't be deleted. Set it inactive instead."))
router.include_router(crud_router(
    prefix="/spa-treatments", tag="Admin: content", model=SpaTreatment, out=SpaTreatmentOut,
    create=SpaTreatmentCreate, update=SpaTreatmentUpdate, order_by=(SpaTreatment.sort_order, SpaTreatment.id),
    resource="spa_treatment", view=_VIEW, manage=_CONTENT))
router.include_router(crud_router(
    prefix="/content-cards", tag="Admin: content", model=ContentCard, out=ContentCardOut, create=ContentCardCreate,
    update=ContentCardUpdate, order_by=(ContentCard.section, ContentCard.sort_order, ContentCard.id),
    resource="content_card", view=_VIEW, manage=_CONTENT, filters={"section": ContentCard.section}))
router.include_router(crud_router(
    prefix="/gallery", tag="Admin: content", model=GalleryImage, out=GalleryImageOut, create=GalleryImageCreate,
    update=GalleryImageUpdate, order_by=(GalleryImage.sort_order, GalleryImage.id), resource="gallery_image",
    view=_VIEW, manage=_CONTENT, filters={"category": GalleryImage.category}))
router.include_router(crud_router(
    prefix="/job-openings", tag="Admin: content", model=JobOpening, out=JobOpeningOut, create=JobOpeningCreate,
    update=JobOpeningUpdate, order_by=(JobOpening.sort_order, JobOpening.id), resource="job_opening",
    view=_VIEW, manage=_CONTENT))


@router.get("/settings", response_model=list[SettingOut], tags=["Admin: settings"])
def list_settings(_: AdminUser = Depends(require(_VIEW)), db: Session = Depends(get_db)):
    return settings_repo.all_settings(db)


@router.put("/settings/{key}", response_model=SettingOut, tags=["Admin: settings"])
def update_setting(key: str, data: SettingUpdate, request: Request,
                   actor: AdminUser = Depends(require(Permission.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return settings_service.update(db, key, data.value, actor, request)


@router.post("/uploads/image", response_model=UploadOut, tags=["Admin: content"],
             summary="Upload a JPG/PNG/WebP image; returns the URL to use in content")
async def upload_image(request: Request, file: UploadFile = File(...),
                       actor: AdminUser = Depends(require(_CONTENT))):
    stored, url = await upload_service.store_image(file)
    await run_in_threadpool(audit.record_now, action="upload.image", actor=actor, resource_type="upload", resource_id=stored.relative_path,
                     details={"size": stored.size, "original_name": stored.original_name}, request=request)
    return UploadOut(url=url, size=stored.size)
