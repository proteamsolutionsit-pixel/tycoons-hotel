from datetime import date, timedelta
from decimal import Decimal

from app.core.timeutil import hotel_today
from app.models import SiteSetting
from app.services.availability import peak_occupancy
from tests.conftest import stay


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_site_settings_are_public_but_tax_is_not(client):
    s = client.get("/api/v1/site").json()["settings"]
    assert s["address_street"] == "[Street address]"
    assert s["amenities"][0] == "Fishy Tales"
    assert "room_tax_percent" not in s


def test_rooms_listed_in_order(client):
    rooms = client.get("/api/v1/rooms").json()
    assert [r["slug"] for r in rooms] == ["twin-room", "premium-room", "deluxe-room", "tycoon-suite"]
    assert rooms[3]["is_signature"] is True


def test_gallery_filter_home_and_pagination(client):
    all_ = client.get("/api/v1/gallery").json()
    assert all_["total"] == 16
    wellness = client.get("/api/v1/gallery", params={"category": "wellness"}).json()
    assert wellness["total"] == 5 and all(i["category"] == "wellness" for i in wellness["items"])
    home = client.get("/api/v1/gallery", params={"home": "true"}).json()["items"]
    assert [i["alt"] for i in home] == ["Indoor pool", "Suite living area", "Spa candles and oils",
                                        "Restaurant table setting"]
    page = client.get("/api/v1/gallery", params={"limit": 5, "offset": 15}).json()
    assert len(page["items"]) == 1
    assert client.get("/api/v1/gallery", params={"category": "bogus"}).status_code == 422


def test_cards_treatments_openings(client):
    assert len(client.get("/api/v1/content/cards", params={"section": "dining_menu"}).json()) == 3
    assert len(client.get("/api/v1/content/cards", params={"section": "lounge_spaces"}).json()) == 2
    assert [t["form_label"] for t in client.get("/api/v1/spa/treatments").json()] == [
        "Soothing Massage", "Tailored Therapy", "Wellness Ritual"]
    assert len(client.get("/api/v1/careers/openings").json()) == 3


def test_availability_prices_come_from_database(client):
    r = client.get("/api/v1/bookings/availability", params={**stay(nights=3), "adults": 2})
    assert r.status_code == 200
    body = r.json()
    premium = next(q for q in body["rooms"] if q["slug"] == "premium-room")
    assert body["nights"] == 3
    assert premium["nightly_rate_paise"] == 750000
    assert premium["total_paise"] == 3 * 750000
    assert premium["available_rooms"] == 16 and premium["bookable"]


def test_availability_applies_tax(client, db):
    db.get(SiteSetting, "room_tax_percent").value = 12
    db.commit()
    q = client.get("/api/v1/bookings/availability", params={**stay(nights=1), "adults": 1}).json()["rooms"][0]
    assert q["tax_paise"] == 78000 and q["total_paise"] == 728000
    assert Decimal(q["tax_percent"]) == Decimal("12")


def test_availability_rejects_bad_dates(client):
    past = hotel_today() - timedelta(days=1)
    r = client.get("/api/v1/bookings/availability",
                   params={"check_in": past.isoformat(), "check_out": hotel_today().isoformat()})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_dates"

    s = stay()
    r = client.get("/api/v1/bookings/availability", params={"check_in": s["check_out"], "check_out": s["check_in"]})
    assert r.status_code == 400

    r = client.get("/api/v1/bookings/availability", params=stay(nights=31))
    assert r.json()["error"]["code"] == "stay_too_long"


def test_party_too_large_is_not_bookable(client):
    rooms = client.get("/api/v1/bookings/availability", params={**stay(), "adults": 3}).json()["rooms"]
    assert all(not r["fits_party"] and not r["bookable"] for r in rooms)


def test_peak_occupancy_counts_per_night_not_overlaps():
    d = date(2030, 1, 1)
    day = lambda n: d + timedelta(days=n)  # noqa: E731
    # Two stays that each overlap the window but not each other: peak is 1, not 2
    stays = [(day(0), day(2)), (day(2), day(4))]
    assert peak_occupancy(stays, day(0), day(4)) == 1
    stays.append((day(1), day(3)))
    assert peak_occupancy(stays, day(0), day(4)) == 2


def test_unknown_route_returns_json_404(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
