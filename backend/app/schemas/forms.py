"""Request bodies for the public forms. Option lists mirror the <select>s in
the original design exactly."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import GuestType
from app.schemas.common import OptionalText, PersonName, Phone

PartySize = Literal["2", "3", "4", "5-8", "9+"]
Occasion = Literal["None", "Birthday", "Anniversary", "Business dinner", "Other"]
ContactTopic = Literal["Room reservation", "Business lounge", "Fishy Tales", "Kai Wellness Spa", "Other"]


class TableReservationIn(BaseModel):
    name: PersonName
    phone: Phone
    date: dt.date
    time: dt.time
    guests: PartySize
    occasion: Occasion = "None"
    requests: OptionalText = Field(default=None, max_length=1000)


class SpaAppointmentIn(BaseModel):
    name: PersonName
    phone: Phone
    treatment_id: int | None = Field(default=None, description="Omit or null for 'Not sure - advise me'")
    guest_type: GuestType
    date: dt.date
    time: dt.time


class BusinessEnquiryIn(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    name: PersonName
    email: EmailStr
    phone: Phone
    date: dt.date | None = None
    attendees: int | None = Field(default=None, ge=1, le=500)
    requirements: OptionalText = Field(default=None, max_length=2000)

    @field_validator("company")
    @classmethod
    def _company(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please enter your company name")
        if any(c in v for c in "<>{}\\"):
            raise ValueError("Please remove special characters")
        return v


class ContactEnquiryIn(BaseModel):
    name: PersonName
    email: EmailStr
    phone: Phone | None = None
    topic: ContactTopic
    message: str = Field(min_length=1, max_length=2000)
    consent: bool

    @field_validator("message")
    @classmethod
    def _msg(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Please tell us a little more")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please agree to be contacted about your enquiry")
        return v


class NewsletterIn(BaseModel):
    email: EmailStr
    consent: bool

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please tick the box to confirm your subscription")
        return v


class SubmissionAck(BaseModel):
    id: int
    message: str
