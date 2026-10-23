from __future__ import annotations

import re
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

T = TypeVar("T")

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHONE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")


def _clean_text(v: str) -> str:
    v = _CONTROL.sub("", v).strip()
    return v


def _person_name(v: str) -> str:
    v = re.sub(r"\s+", " ", _clean_text(v))
    if len(v) < 2:
        raise ValueError("Please enter your full name")
    if any(c in v for c in "<>{}[]\\=;"):
        raise ValueError("Please use letters, spaces and basic punctuation only")
    return v


def _phone(v: str) -> str:
    v = _clean_text(v)
    if not _PHONE.match(v) or sum(c.isdigit() for c in v) < 7:
        raise ValueError("Please enter a valid phone number")
    return v


def _optional_text(v: str | None) -> str | None:
    if v is None:
        return None
    v = _clean_text(v)
    return v or None


CleanStr = Annotated[str, AfterValidator(_clean_text)]
PersonName = Annotated[str, Field(max_length=120), AfterValidator(_person_name)]
Phone = Annotated[str, Field(max_length=32), AfterValidator(_phone)]
OptionalText = Annotated[str | None, Field(default=None, max_length=2000), AfterValidator(_optional_text)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str
