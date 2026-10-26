"""Multi-room bookings: a party larger than one room books several rooms of
the same type in one booking - priced, held and confirmed as a unit."""
from app.models import Booking, RoomType
from app.services.availability import fits_party, peak_occupancy, rooms_needed
from tests.conftest import FakeGateway, booking_payload, stay

AV = "/api/v1/bookings/availability"


def _quote(client, slug, **params):
    rooms = client.get(AV, params={**stay(), **params}).json()["rooms"]
    return next(r for r in rooms if r["slug"] == slug)


def test_rooms_needed_rules():
    room = RoomType(max_adults=2, max_children=1)
    assert rooms_needed(room, 2, 1) == 1
    assert rooms_needed(room, 4, 0) == 2
    assert rooms_needed(room, 3, 2) == 2
    assert rooms_needed(room, 5, 0) == 3
    assert rooms_needed(room, 1, 3) is None            # each room needs an adult
    assert not fits_party(room, 2, 0, rooms=3)          # three rooms for two adults: no


def test_peak_occupancy_weights_rooms():
    from datetime import date, timedelta
    d = date(2030, 1, 1)
    assert peak_occupancy([(d, d + timedelta(days=2), 3), (d, d + timedelta(days=1), 1)], d, d + timedelta(days=2)) == 4


def test_four_adults_get_a_two_room_quote_at_twice_the_price(client):
    one = _quote(client, "premium-room", adults=2)
    two = _quote(client, "premium-room", adults=4)
    assert one["room_count"] == 1 and two["room_count"] == 2 and two["bookable"]
    assert two["total_paise"] == 2 * one["total_paise"] and two["nightly_rate_paise"] == one["nightly_rate_paise"]


def test_booking_two_rooms_holds_two_rooms_for_one_payment(client, gateway, db):
    r = client.post("/api/v1/bookings", json=booking_payload(adults=4))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["booking"]["room_count"] == 2
    assert body["booking"]["total_paise"] == 2 * 1500000        # 2 rooms x 2 nights x Rs 7,500
    assert body["checkout"]["amount"] == body["booking"]["total_paise"]
    row = db.query(Booking).one()
    assert row.room_count == 2
    # availability drops by two rooms for those nights
    room = db.query(RoomType).filter_by(slug="premium-room").one()
    assert _quote(client, "premium-room", adults=2)["available_rooms"] == room.total_rooms - 2


def test_two_rooms_refused_when_only_one_is_free(client, gateway, db):
    room = db.query(RoomType).filter_by(slug="premium-room").one()
    room.total_rooms = 1
    db.commit()
    q = _quote(client, "premium-room", adults=4)
    assert q["room_count"] == 2 and not q["bookable"]
    r = client.post("/api/v1/bookings", json=booking_payload(adults=4))
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"


def test_room_count_must_sleep_the_party(client, gateway):
    r = client.post("/api/v1/bookings", json=booking_payload(adults=4, room_count=1))
    assert r.status_code == 400 and r.json()["error"]["code"] == "party_too_large"
    r = client.post("/api/v1/bookings", json=booking_payload(adults=2, room_count=5))
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_many_rooms"


def test_guest_may_choose_extra_rooms(client, gateway):
    r = client.post("/api/v1/bookings", json=booking_payload(adults=2, room_count=2))
    assert r.status_code == 201 and r.json()["booking"]["room_count"] == 2


def test_paid_two_room_booking_counts_two_in_admin(client, gateway, admin_headers, db):
    res = client.post("/api/v1/bookings", json=booking_payload(adults=4, days_ahead=0, nights=1)).json()
    order = res["checkout"]["order_id"]
    pay = gateway.pay(order)
    v = client.post("/api/v1/payments/verify", json={"razorpay_order_id": order, "razorpay_payment_id": pay["id"],
                                                     "razorpay_signature": FakeGateway.sign(order, pay["id"])})
    assert v.json()["booking"]["status"] == "confirmed"
    dash = client.get("/api/v1/admin/dashboard").json()
    assert dash["rooms_sold_tonight"] == 2
    occ = client.get("/api/v1/admin/occupancy", params={"days": 1}).json()
    premium = next(r for r in occ["rooms"] if r["slug"] == "premium-room")
    assert premium["booked"] == [2]
    row = client.get("/api/v1/admin/bookings").json()["items"][0]
    assert row["room_count"] == 2
