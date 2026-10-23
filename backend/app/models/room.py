from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RoomType(TimestampMixin, Base):
    """A bookable category of room (Twin, Premium, Deluxe, Tycoon Suite)."""

    __tablename__ = "room_types"
    __table_args__ = (
        CheckConstraint("base_rate_paise >= 0", name="rate_non_negative"),
        CheckConstraint("total_rooms >= 0", name="inventory_non_negative"),
        CheckConstraint("max_adults >= 1", name="max_adults_positive"),
        CheckConstraint("max_children >= 0", name="max_children_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    summary: Mapped[str] = mapped_column(String(500))          # homepage carousel blurb
    description: Mapped[str] = mapped_column(Text)              # Rooms page paragraph
    image_url: Mapped[str] = mapped_column(String(500))
    image_alt: Mapped[str] = mapped_column(String(200), default="")
    size_label: Mapped[str] = mapped_column(String(120), default="")
    bed_label: Mapped[str] = mapped_column(String(120), default="")
    view_label: Mapped[str] = mapped_column(String(120), default="")
    occupancy_label: Mapped[str] = mapped_column(String(120), default="")
    max_adults: Mapped[int] = mapped_column(Integer, default=2)
    max_children: Mapped[int] = mapped_column(Integer, default=1)
    base_rate_paise: Mapped[int] = mapped_column(Integer)      # per night, before tax
    total_rooms: Mapped[int] = mapped_column(Integer)          # sellable inventory
    is_signature: Mapped[bool] = mapped_column(Boolean, default=False)  # gold-framed card (Tycoon Suite)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
