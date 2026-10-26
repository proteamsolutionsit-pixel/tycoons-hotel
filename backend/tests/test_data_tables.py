"""Data-table features on every admin list: search, sorting, page size and
CSV export (admin only, formula-safe, audited)."""
import csv
import io

import pytest

from app.models import AuditLog
from tests.conftest import STAFF_PW, create_booking, login

A = "/api/v1/admin"


def _csv(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig"))))


def _enquiry(client, name, email, message="Hello there"):
    r = client.post("/api/v1/enquiries/contact", json={"name": name, "email": email, "topic": "Other",
                                                       "message": message, "consent": True})
    assert r.status_code == 201, r.text


# -- Bookings & payments ------------------------------------------------------
def test_bookings_export_follows_search_and_is_audited(client, admin_headers, db):
    create_booking(client, guest_name="Asha Rao")
    create_booking(client, guest_name="Vikram Iyer", guest_email="vikram@example.com", days_ahead=20)
    rows = _csv(client.get(f"{A}/bookings/export", params={"q": "Asha"}))
    assert [r["guest_name"] for r in rows] == ["Asha Rao"]
    assert rows[0]["total_inr"] == "15000.00" and rows[0]["status"] == "pending_payment"
    entry = db.query(AuditLog).filter_by(action="booking.export").one()
    assert entry.details == {"rows": 1, "filters": {"q": "Asha", "sort": "created_at", "order": "desc"}}


def test_bookings_page_size_up_to_200(client, admin_headers):
    assert client.get(f"{A}/bookings", params={"limit": 200}).status_code == 200
    assert client.get(f"{A}/bookings", params={"limit": 201}).status_code == 422


def test_payments_sort_by_guest_and_export(client, admin_headers):
    create_booking(client, guest_name="Zara Khan")
    create_booking(client, guest_name="Arjun Mehta", days_ahead=20)
    names = [p["guest_name"] for p in client.get(f"{A}/payments", params={"sort": "guest", "order": "asc"}).json()["items"]]
    assert names == ["Arjun Mehta", "Zara Khan"]
    rows = _csv(client.get(f"{A}/payments/export", params={"sort": "guest", "order": "desc"}))
    assert [r["guest_name"] for r in rows] == ["Zara Khan", "Arjun Mehta"] and rows[0]["amount_inr"] == "15000.00"


# -- Guest requests -------------------------------------------------------------
def test_submissions_sort_and_export_neutralise_formulas(client, admin_headers, db):
    _enquiry(client, "Bina Das", "bina@example.com")
    _enquiry(client, "Amit Roy", "amit@example.com", message="=HYPERLINK(\"http://evil\")")
    names = [i["name"] for i in client.get(f"{A}/submissions/enquiries", params={"sort": "name", "order": "asc"}).json()["items"]]
    assert names == ["Amit Roy", "Bina Das"]
    rows = _csv(client.get(f"{A}/submissions/enquiries/export", params={"sort": "name", "order": "asc"}))
    assert [r["name"] for r in rows] == ["Amit Roy", "Bina Das"]
    assert rows[0]["message"].startswith("'=")
    assert db.query(AuditLog).filter_by(action="enquiries.export").count() == 1


def test_newsletter_sort_and_export(client, admin_headers):
    for email in ("b@example.com", "a@example.com"):
        assert client.post("/api/v1/newsletter", json={"email": email, "consent": True}).status_code == 201
    emails = [s["email"] for s in client.get(f"{A}/submissions/newsletter", params={"sort": "email", "order": "asc"}).json()["items"]]
    assert emails == ["a@example.com", "b@example.com"]
    rows = _csv(client.get(f"{A}/submissions/newsletter/export"))
    assert {r["email"] for r in rows} == {"a@example.com", "b@example.com"} and rows[0]["active"] == "yes"


def test_unknown_submission_kind_export_is_404(client, admin_headers):
    assert client.get(f"{A}/submissions/nope/export").status_code == 404


# -- Rooms & content (generic tables) --------------------------------------------
def test_crud_search_sort_and_export(client, admin_headers):
    found = client.get(f"{A}/room-types", params={"q": "deluxe"}).json()
    assert [r["slug"] for r in found["items"]] == ["deluxe-room"]
    rates = [r["base_rate_paise"] for r in client.get(f"{A}/room-types", params={"sort": "base_rate_paise", "order": "desc"}).json()["items"]]
    assert rates == sorted(rates, reverse=True)
    assert client.get(f"{A}/room-types", params={"sort": "no_such_column"}).status_code == 422
    rows = _csv(client.get(f"{A}/room-types/export", params={"sort": "name"}))
    assert [r["name"] for r in rows] == sorted(r["name"] for r in rows) and "base_rate_paise" in rows[0]
    # LIKE wildcards in the search text are literal
    assert client.get(f"{A}/room-types", params={"q": "%"}).json()["total"] == 0


def test_get_by_id_still_works_next_to_export(client, admin_headers):
    assert client.get(f"{A}/room-types/1").status_code == 200


# -- Permissions -----------------------------------------------------------------
@pytest.mark.parametrize("path", ["/bookings/export", "/payments/export", "/submissions/enquiries/export",
                                  "/submissions/newsletter/export", "/room-types/export", "/gallery/export"])
def test_exports_are_admin_only(client, path):
    login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.get(A + path).status_code == 403


def test_staff_can_still_search_and_sort_what_they_can_view(client):
    login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.get(f"{A}/bookings", params={"q": "x", "sort": "guest", "order": "asc", "limit": 100}).status_code == 200
    assert client.get(f"{A}/room-types", params={"q": "room", "sort": "name"}).status_code == 200
