"""Booking-request mode: no online payment. A guest's booking is recorded as a
request, emailed to the hotel's configured recipients (and acknowledged to the
guest), holds no room, and is confirmed or declined by staff."""
import pytest

from app.models import AuditLog, Booking, Payment, PaymentGatewaySettings, SiteSetting
from app.models.enums import BookingStatus
from app.services import notifications
from tests.conftest import booking_payload, stay

AV = "/api/v1/bookings/availability"
HOTEL = "reservations.desk@tycoons.example.com"


@pytest.fixture
def request_mode(db):
    db.add(PaymentGatewaySettings(id=1, mode="request", key_id=""))
    row = db.get(SiteSetting, "booking_request_emails")
    row.value = HOTEL
    db.commit()


@pytest.fixture
def sent(monkeypatch):
    mails = []
    monkeypatch.setattr(notifications, "send_mail", lambda to, subject, body: mails.append((to, subject, body)))
    return mails


def _request(client, **kw):
    r = client.post("/api/v1/bookings", json=booking_payload(**kw))
    assert r.status_code == 201, r.text
    return r.json()


def test_availability_announces_request_mode(client, request_mode):
    assert client.get(AV, params=stay()).json()["booking_mode"] == "request"


def test_pay_mode_is_the_default(client):
    assert client.get(AV, params=stay()).json()["booking_mode"] == "pay"


def test_request_is_recorded_without_payment_and_emailed(client, request_mode, sent, db):
    body = _request(client, room="twin-room", special_requests="Early check-in please")
    assert body["checkout"] is None
    b = body["booking"]
    assert b["status"] == "requested" and b["hold_expires_at"] is None and b["payment_status"] is None
    assert db.query(Payment).count() == 0
    hotel = [m for m in sent if m[0] == HOTEL]
    guest = [m for m in sent if m[0] == "asha@example.com"]
    assert len(hotel) == 1 and len(guest) == 1
    subject, text = hotel[0][1], hotel[0][2]
    assert subject.startswith(f"Booking request {b['reference']} - Twin Room")
    for expected in ("Asha Rao", "asha@example.com", "+91 98450 12345", "Early check-in please",
                     "no payment taken", f"/admin/bookings/{db.query(Booking).one().id}"):
        assert expected in text
    assert "No payment has been taken" in guest[0][2]


def test_request_holds_no_room(client, request_mode, sent, db):
    before = next(r for r in client.get(AV, params=stay()).json()["rooms"] if r["slug"] == "premium-room")["available_rooms"]
    _request(client)
    after = next(r for r in client.get(AV, params=stay()).json()["rooms"] if r["slug"] == "premium-room")["available_rooms"]
    assert after == before


def test_replayed_request_is_not_emailed_twice(client, request_mode, sent):
    headers = {"Idempotency-Key": "abcdef0123456789abcdef"}
    r1 = client.post("/api/v1/bookings", json=booking_payload(), headers=headers)
    r2 = client.post("/api/v1/bookings", json=booking_payload(), headers=headers)
    assert r1.json()["booking"]["reference"] == r2.json()["booking"]["reference"]
    assert len([m for m in sent if m[0] == HOTEL]) == 1


def test_recipients_fall_back_to_hotel_notify_email(client, db, sent, settings):
    db.add(PaymentGatewaySettings(id=1, mode="request", key_id=""))
    db.commit()
    settings.hotel_notify_email = "fallback@tycoons.example.com"
    try:
        _request(client)
    finally:
        settings.hotel_notify_email = ""
    assert any(m[0] == "fallback@tycoons.example.com" for m in sent)


def test_staff_confirm_a_request(client, request_mode, sent, admin_headers, db):
    ref = _request(client)["booking"]["reference"]
    bid = db.query(Booking).filter_by(reference=ref).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/confirm", json={"note": "Confirmed by phone"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    confirmation = [m for m in sent if m[1].startswith("Booking confirmed")]
    assert confirmation and "Amount payable at the hotel" in confirmation[0][2]
    assert db.query(AuditLog).filter_by(action="booking.confirm_request").count() == 1
    # once confirmed it occupies the rooms
    assert db.query(Booking).filter_by(reference=ref).one().status == BookingStatus.CONFIRMED


def test_confirm_refused_when_rooms_are_gone(client, request_mode, sent, admin_headers, db):
    from app.models import RoomType
    ref = _request(client)["booking"]["reference"]
    room = db.query(RoomType).filter_by(slug="premium-room").one()
    room.total_rooms = 0
    db.commit()
    bid = db.query(Booking).filter_by(reference=ref).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/confirm", json={"note": "try"}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"


def test_staff_decline_a_request(client, request_mode, sent, admin_headers, db):
    ref = _request(client)["booking"]["reference"]
    bid = db.query(Booking).filter_by(reference=ref).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel", json={"reason": "No rooms for these dates", "refund": False},
                    headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_dashboard_counts_open_requests(client, request_mode, sent, admin_headers):
    _request(client)
    assert client.get("/api/v1/admin/dashboard").json()["alerts"]["booking_requests"] == 1


def test_request_mode_is_chosen_in_payment_settings(client, admin_headers):
    r = client.put("/api/v1/admin/payment-settings", json={"mode": "request"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["active"] == "request"


def test_recipient_setting_is_validated_and_private(client, admin_headers):
    url = "/api/v1/admin/settings/booking_request_emails"
    assert client.put(url, json={"value": "not-an-email"}, headers=admin_headers).status_code == 422
    assert client.put(url, json={"value": "a@tycoons.example.com, b@tycoons.example.com"}, headers=admin_headers).status_code == 200
    assert "booking_request_emails" not in client.get("/api/v1/site").json()["settings"]


def test_sendmail_transport_pipes_the_message(monkeypatch, settings):
    import subprocess

    from app.services import mailer
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append((args, kw["input"])))
    settings.smtp_host = "sendmail"
    try:
        mailer.send_mail("desk@tycoons.example.com", "Booking request TYC1", "Hello")
    finally:
        settings.smtp_host = ""
    assert calls[0][0] == ["/usr/sbin/sendmail", "-t", "-i"]
    assert b"To: desk@tycoons.example.com" in calls[0][1] and b"Subject: Booking request TYC1" in calls[0][1]
