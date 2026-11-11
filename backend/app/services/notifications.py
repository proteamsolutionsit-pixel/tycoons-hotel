"""Emails sent after a state change has been committed."""
from __future__ import annotations

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.models import Booking
from app.services.mailer import notify_hotel, send_mail


def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def _paid(b: Booking) -> bool:
    return any(p.status.value in ("captured", "refund_pending", "refunded") for p in b.payments)


def _stay_lines(b: Booking) -> list[str]:
    return [
        f"Booking reference: {b.reference}",
        f"Room: {b.room_type.name}" + (f" x {b.room_count}" if b.room_count > 1 else ""),
        f"Check-in: {b.check_in:%A, %d %B %Y}",
        f"Check-out: {b.check_out:%A, %d %B %Y} ({b.nights} night{'s' if b.nights != 1 else ''})",
        f"Guests: {b.adults} adult{'s' if b.adults != 1 else ''}"
        + (f", {b.children} child{'ren' if b.children != 1 else ''}" if b.children else ""),
        *([f"Includes: {b.inclusions}"] if b.inclusions else []),
    ]


def booking_requested(background: BackgroundTasks, b: Booking, recipients: list[str]) -> None:
    """Booking-request mode: the full request to the hotel, and an acknowledgement to the guest."""
    s = get_settings()
    rate = f"{rupees(b.nightly_rate_paise)} per room per night"
    if b.single_room_count and b.single_rate_paise is not None:
        rate += f" (single occupancy {rupees(b.single_rate_paise)} for {b.single_room_count} room(s))"
    hotel_body = "\n".join([
        "A new booking request has been received from the website.",
        "",
        *_stay_lines(b),
        f"Rate: {rate}",
        f"Estimated total: {rupees(b.total_paise)} (no payment taken)",
        "",
        f"Guest: {b.guest_name}",
        f"Email: {b.guest_email}",
        f"Phone: {b.guest_phone}",
        f"Special requests: {b.special_requests or '-'}",
        "",
        f"Confirm or decline in the admin: {s.public_base_url.rstrip('/')}/admin/bookings/{b.id}",
    ])
    subject = (f"Booking request {b.reference} - {b.room_type.name}"
               f"{' x ' + str(b.room_count) if b.room_count > 1 else ''}, {b.check_in:%d %b} to {b.check_out:%d %b %Y}")
    for to in recipients:
        background.add_task(send_mail, to, subject, hotel_body)
    guest_body = "\n".join([
        f"Dear {b.guest_name},",
        "",
        f"Thank you for your booking request at {s.hotel_name}. We have received it and our reservations",
        "team will contact you shortly to confirm. No payment has been taken.",
        "",
        *_stay_lines(b),
        f"Estimated total: {rupees(b.total_paise)}",
        "",
        s.hotel_name,
    ])
    background.add_task(send_mail, b.guest_email, f"We received your booking request - {b.reference}", guest_body)


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
        *([f"Includes: {b.inclusions}"] if b.inclusions else []),
        (f"Amount paid: {rupees(b.total_paise)}" if _paid(b) else f"Amount payable at the hotel: {rupees(b.total_paise)}"),
        "",
        "We look forward to welcoming you.",
        hotel,
    ]
    background.add_task(send_mail, b.guest_email, f"Booking confirmed - {b.reference}", "\n".join(lines))
    background.add_task(notify_hotel, f"New booking {b.reference} ({b.room_type.name})",
                        f"{b.guest_name} <{b.guest_email}>, {b.guest_phone}\n"
                        f"{b.check_in} to {b.check_out}, {b.adults}A/{b.children}C\n"
                        f"{'Paid' if _paid(b) else 'Payable at the hotel'} {rupees(b.total_paise)}")


def booking_needs_review(background: BackgroundTasks, b: Booking) -> None:
    background.add_task(notify_hotel, f"ACTION NEEDED: payment for {b.reference} needs review",
                        f"A payment was captured for booking {b.reference} after its hold lapsed and no "
                        f"{b.room_type.name} is free for {b.check_in} to {b.check_out}. Rehouse the guest or "
                        f"refund from the admin.")


def submission_received(background: BackgroundTasks, subject: str, body: str) -> None:
    background.add_task(notify_hotel, subject, body)
