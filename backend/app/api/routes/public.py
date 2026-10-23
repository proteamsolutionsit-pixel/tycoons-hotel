"""Read-only content for the public site."""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ContentCard, GalleryImage, JobOpening, RoomType, SpaTreatment
from app.models.enums import CardSection, GalleryCategory
from app.repositories import settings as settings_repo
from app.schemas.common import Page
from app.schemas.content import (
    ContentCardPublic,
    GalleryImagePublic,
    JobOpeningPublic,
    RoomTypePublic,
    SiteContent,
    SpaTreatmentPublic,
)

log = logging.getLogger("app.health")
router = APIRouter(tags=["Site content"])


@router.get("/health/live", tags=["System"], summary="Liveness: the process is up (no dependencies checked)")
def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready", tags=["System"], summary="Readiness: database reachable and schema up to date")
@router.get("/health", tags=["System"], include_in_schema=False)
def ready(db: Session = Depends(get_db)):
    # Deliberately no details in the body: this endpoint is public.
    try:
        db.execute(text("SELECT 1"))
        current = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception:
        log.exception("Readiness check failed: database")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    if current != schema_head():
        log.error("Readiness check failed: schema not at head", extra={"db": current, "head": schema_head()})
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}


@lru_cache
def schema_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.core.config import BACKEND_DIR
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


@router.get("/site", response_model=SiteContent, summary="Contact details, hours and other site-wide settings")
def site(db: Session = Depends(get_db)):
    return SiteContent(settings=settings_repo.public_settings(db))


@router.get("/rooms", response_model=list[RoomTypePublic], summary="Active room types")
def rooms(db: Session = Depends(get_db)):
    return db.execute(select(RoomType).where(RoomType.is_active.is_(True))
                      .order_by(RoomType.sort_order, RoomType.id)).scalars().all()


@router.get("/spa/treatments", response_model=list[SpaTreatmentPublic])
def spa_treatments(db: Session = Depends(get_db)):
    return db.execute(select(SpaTreatment).where(SpaTreatment.is_active.is_(True))
                      .order_by(SpaTreatment.sort_order, SpaTreatment.id)).scalars().all()


@router.get("/content/cards", response_model=list[ContentCardPublic])
def content_cards(section: CardSection, db: Session = Depends(get_db)):
    return db.execute(select(ContentCard).where(ContentCard.section == section, ContentCard.is_active.is_(True))
                      .order_by(ContentCard.sort_order, ContentCard.id)).scalars().all()


@router.get("/gallery", response_model=Page[GalleryImagePublic], summary="Gallery photos (filterable, paginated)")
def gallery(category: GalleryCategory | None = None,
            home: bool = Query(False, description="Only the photos featured on the homepage"),
            limit: int = Query(60, ge=1, le=100), offset: int = Query(0, ge=0),
            db: Session = Depends(get_db)):
    stmt = select(GalleryImage).where(GalleryImage.is_active.is_(True))
    if category:
        stmt = stmt.where(GalleryImage.category == category)
    if home:
        stmt = stmt.where(GalleryImage.on_home.is_(True))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    order = (GalleryImage.home_order, GalleryImage.id) if home else (GalleryImage.sort_order, GalleryImage.id)
    items = db.execute(stmt.order_by(*order).limit(limit).offset(offset)).scalars().all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/careers/openings", response_model=list[JobOpeningPublic])
def openings(db: Session = Depends(get_db)):
    return db.execute(select(JobOpening).where(JobOpening.is_active.is_(True))
                      .order_by(JobOpening.sort_order, JobOpening.id)).scalars().all()
