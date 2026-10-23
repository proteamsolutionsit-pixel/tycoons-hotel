"""Site settings: shape validation, updates and their audit trail."""
from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.models import AdminUser, SiteSetting
from app.services import audit

_GOOGLE_MAPS_EMBED = re.compile(r"^https://(www\.)?google\.[a-z.]{2,10}/maps/embed\?[^\s<>\"']{1,1500}$")


def _bad(msg: str) -> None:
    raise AppError(msg, code="validation_error", status_code=422, details=[{"field": "value", "message": msg}])


def validate(row: SiteSetting, value: Any) -> None:
    """Keep each setting the same shape as its seeded value, so the site never
    receives something it can't render."""
    current = row.value
    if row.key == "room_tax_percent":
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
            _bad("Enter a percentage between 0 and 100.")
        return
    if row.key == "map_embed_url":
        if value and (not isinstance(value, str) or not _GOOGLE_MAPS_EMBED.match(value)):
            _bad("Use the src of a Google Maps embed (https://www.google.com/maps/embed?…).")
        return
    if row.key == "cancellation_policy":
        if not isinstance(value, str) or not 3 <= len(value.strip()) <= 4000:
            _bad("Enter the policy text (up to 4000 characters).")
        return
    if isinstance(current, str):
        if not isinstance(value, str) or len(value) > 500:
            _bad("Enter text (up to 500 characters).")
    elif isinstance(current, list):
        if not isinstance(value, list) or len(value) > 30:
            _bad("Enter a list (up to 30 items).")
        if current and isinstance(current[0], dict):
            for item in value:
                if not (isinstance(item, dict) and set(item) <= {"label", "value"}
                        and isinstance(item.get("label"), str) and isinstance(item.get("value"), str)
                        and len(item["label"]) <= 200 and len(item["value"]) <= 200):
                    _bad("Each row needs a label and a value (up to 200 characters each).")
        elif not all(isinstance(v, str) and len(v) <= 200 for v in value):
            _bad("Each item must be text (up to 200 characters).")
    if row.key.endswith("_url") and isinstance(value, str) and value and not value.startswith(("https://", "/")):
        _bad("Links must start with https:// or /.")


def update(db: Session, key: str, value: Any, actor: AdminUser, request: Request) -> SiteSetting:
    row = db.get(SiteSetting, key)
    if row is None:
        raise NotFound("Unknown setting.")
    validate(row, value)
    old = row.value
    row.value = value
    audit.record(db, action="setting.update", actor=actor, resource_type="site_setting", resource_id=key,
                 details={"from": old, "to": value}, request=request)
    db.commit()
    db.refresh(row)
    return row
