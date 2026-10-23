"""Content the hotel edits from the admin. Page copy that is part of the
design (headlines, intros) stays in the React components."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base, TimestampMixin, enum_col
from app.models.enums import CardSection, GalleryCategory, GalleryLayout


class SpaTreatment(TimestampMixin, Base):
    __tablename__ = "spa_treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))          # card title: "Soothing Massages"
    form_label: Mapped[str] = mapped_column(String(120))    # appointment option: "Soothing Massage"
    description: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(500))
    image_alt: Mapped[str] = mapped_column(String(200), default="")
    duration_label: Mapped[str] = mapped_column(String(60), default="")
    price_label: Mapped[str] = mapped_column(String(60), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContentCard(TimestampMixin, Base):
    __tablename__ = "content_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    section: Mapped[CardSection] = mapped_column(enum_col(CardSection), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(500))
    image_alt: Mapped[str] = mapped_column(String(200), default="")
    meta: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GalleryImage(TimestampMixin, Base):
    __tablename__ = "gallery_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(500))
    alt: Mapped[str] = mapped_column(String(200))
    category: Mapped[GalleryCategory] = mapped_column(enum_col(GalleryCategory, 16), index=True)
    layout: Mapped[GalleryLayout] = mapped_column(enum_col(GalleryLayout, 16), default=GalleryLayout.NORMAL)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    on_home: Mapped[bool] = mapped_column(Boolean, default=False)   # homepage "A glimpse..." strip
    home_order: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class JobOpening(TimestampMixin, Base):
    __tablename__ = "job_openings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    department: Mapped[str] = mapped_column(String(120))
    employment_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SiteSetting(Base):
    """Key/value settings shown across the site: address, phones, opening
    hours, the practical-details strips, amenities ticker and so on."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    label: Mapped[str] = mapped_column(String(120))
    group: Mapped[str] = mapped_column(String(40), default="general")
    help_text: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
