"""Emails sent after a state change has been committed."""
from __future__ import annotations

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.models import Booking
from app.services.mailer import notify_hotel, send_mail


def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def booking_confirmed(background: BackgroundTasks, b: Booking) -> None:
    hotel = get_settings().hotel_name
    lines = [
        f"Dear {b.guest_name},",
        "",
        f"Your stay at {hotel} is confirmed.",
        "",
        f"Booking reference: {b.reference}",
        f"Room: {b.room_type.name}" + (f" x {b.room_count}" if b.room_count > 1 else ""),
        f"Check-in: {b.check_in:%A, %d %B %Y}",
        f"Check-out: {b.check_out:%A, %d %B %Y} ({b.nights} night{'s' if b.nights != 1 else ''})",
        f"Guests: {b.adults} adult{'s' if b.adults != 1 else ''}"
        + (f", {b.children} child{'ren' if b.children != 1 else ''}" if b.children else ""),
        f"Amount paid: {rupees(b.total_paise)}",
        "",
        "We look forward to welcoming you.",
        hotel,
    ]
    background.add_task(send_mail, b.guest_email, f"Booking confirmed - {b.reference}", "\n".join(lines))
    background.add_task(notify_hotel, f"New booking {b.reference} ({b.room_type.name})",
                        f"{b.guest_name} <{b.guest_email}>, {b.guest_phone}\n"
                        f"{b.check_in} to {b.check_out}, {b.adults}A/{b.children}C\n"
                        f"Paid {rupees(b.total_paise)}")


def booking_needs_review(background: BackgroundTasks, b: Booking) -> None:
    background.add_task(notify_hotel, f"ACTION NEEDED: payment for {b.reference} needs review",
                        f"A payment was captured for booking {b.reference} after its hold lapsed and no "
                        f"{b.room_type.name} is free for {b.check_in} to {b.check_out}. Rehouse the guest or "
                        f"refund from the admin.")


def submission_received(background: BackgroundTasks, subject: str, body: str) -> None:
    background.add_task(notify_hotel, subject, body)
