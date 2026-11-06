from __future__ import annotations

from typing import Any

from app.models.enums import CardSection, GalleryCategory, GalleryLayout
from app.schemas.common import ORMModel


class RoomTypePublic(ORMModel):
    slug: str
    name: str
    summary: str
    description: str
    image_url: str
    image_alt: str
    size_label: str
    bed_label: str
    view_label: str
    occupancy_label: str
    max_adults: int
    max_children: int
    base_rate_paise: int
    single_rate_paise: int | None = None
    inclusions: str = ""
    is_signature: bool


class SpaTreatmentPublic(ORMModel):
    id: int
    slug: str
    name: str
    form_label: str
    description: str
    image_url: str
    image_alt: str
    duration_label: str
    price_label: str


class ContentCardPublic(ORMModel):
    id: int
    section: CardSection
    title: str
    body: str
    image_url: str
    image_alt: str
    meta: str | None


class GalleryImagePublic(ORMModel):
    id: int
    image_url: str
    alt: str
    category: GalleryCategory
    layout: GalleryLayout
    width: int | None
    height: int | None


class JobOpeningPublic(ORMModel):
    id: int
    title: str
    department: str
    employment_type: str
    description: str | None


class SiteContent(ORMModel):
    settings: dict[str, Any]
