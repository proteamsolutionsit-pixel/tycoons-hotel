"""Occupancy-based tariffs: a room with one adult pays the single rate when the
room type has one; inclusions (e.g. breakfast) are shown and recorded."""
from decimal import Decimal

from app.models import Booking, RoomType
from app.services.availability import occupancy_split, quote
from tests.conftest import booking_payload, stay

AV = "/api/v1/bookings/availability"
TWIN = {"base_rate_paise": 450000, "single_rate_paise": 350000, "inclusions": "Complimentary breakfast"}


def _set_twin(db, **values):
    room = db.query(RoomType).filter_by(slug="twin-room").one()
    for k, v in {**TWIN, **values}.items():
        setattr(room, k, v)
    db.commit()
    return room


def _twin_quote(client, **params):
    rooms = client.get(AV, params={**stay(nights=1), **params}).json()["rooms"]
    return next(r for r in rooms if r["slug"] == "twin-room")


def test_occupancy_split_is_even():
    assert occupancy_split(1, 1) == [1]
    assert occupancy_split(3, 2) == [2, 1]
    assert occupancy_split(4, 2) == [2, 2]
    assert occupancy_split(2, 2) == [1, 1]


def test_quote_uses_single_rate_only_for_one_adult_rooms():
    room = RoomType(base_rate_paise=450000, single_rate_paise=350000)
    assert quote(room, 1, Decimal(0), 1, adults=1).subtotal_paise == 350000
    assert quote(room, 1, Decimal(0), 1, adults=2).subtotal_paise == 450000
    q = quote(room, 2, Decimal(0), 2, adults=3)                 # one double + one single, 2 nights
    assert (q.single_rooms, q.nightly_total_paise, q.subtotal_paise) == (1, 800000, 1600000)
    no_single = RoomType(base_rate_paise=750000, single_rate_paise=None)
    assert quote(no_single, 1, Decimal(0), 1, adults=1).subtotal_paise == 750000


def test_availability_quotes_single_and_double_occupancy(client, db):
    _set_twin(db)
    single = _twin_quote(client, adults=1)
    double = _twin_quote(client, adults=2)
    assert single["total_paise"] == 350000 and single["single_rooms"] == 1
    assert double["total_paise"] == 450000 and double["single_rooms"] == 0
    assert single["single_rate_paise"] == 350000 and single["nightly_rate_paise"] == 450000
    assert single["inclusions"] == "Complimentary breakfast"
    # children do not change the occupancy rate
    assert _twin_quote(client, adults=1, children=1)["total_paise"] == 350000


def test_booking_charges_and_records_the_single_rate(client, gateway, db):
    _set_twin(db)
    r = client.post("/api/v1/bookings", json=booking_payload(room="twin-room", adults=1, nights=1))
    assert r.status_code == 201, r.text
    b = r.json()["booking"]
    assert b["total_paise"] == 350000 and r.json()["checkout"]["amount"] == 350000
    assert b["single_room_count"] == 1 and b["single_rate_paise"] == 350000
    assert b["inclusions"] == "Complimentary breakfast"
    row = db.query(Booking).one()
    assert (row.single_room_count, row.single_rate_paise, row.subtotal_paise) == (1, 350000, 350000)


def test_rates_are_public_and_editable_in_admin(client, admin_headers, db):
    room = _set_twin(db, single_rate_paise=None, inclusions="")
    r = client.patch(f"/api/v1/admin/room-types/{room.id}", json=TWIN, headers=admin_headers)
    assert r.status_code == 200 and r.json()["single_rate_paise"] == 350000
    public = next(x for x in client.get("/api/v1/rooms").json() if x["slug"] == "twin-room")
    assert (public["base_rate_paise"], public["single_rate_paise"], public["inclusions"]) == (450000, 350000, "Complimentary breakfast")
    # clearing the single rate falls back to the standard rate
    assert client.patch(f"/api/v1/admin/room-types/{room.id}", json={"single_rate_paise": None}, headers=admin_headers).status_code == 200
    assert _twin_quote(client, adults=1)["total_paise"] == 450000
