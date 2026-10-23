"""Read-only content for the public site."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ContentCard, GalleryImage, JobOpening, RoomType, SpaTreatment
from app.models.enums import CardSection, GalleryCategory
from app.repositories import settings as settings_repo
from app.schemas.common import Page
from app.schemas.content import (ContentCardPublic, GalleryImagePublic, JobOpeningPublic, RoomTypePublic,
                                 SiteContent, SpaTreatmentPublic)

router = APIRouter(tags=["Site content"])


@router.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


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
