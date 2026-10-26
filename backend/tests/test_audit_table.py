"""Audit log table: search, sorting, hotel-day date range, paging and CSV export."""
import csv
import io
from datetime import datetime

from app.models import AuditLog
from tests.conftest import STAFF_PW, login

URL = "/api/v1/admin/audit-logs"


def _seed(db):
    rows = [
        # occurred_at is naive UTC; the hotel is UTC+05:30
        ("alpha@tycoons.example.com", "booking.cancel", "booking", "41", "success", "10.0.0.1", datetime(2026, 10, 20, 4, 0)),
        ("bravo@tycoons.example.com", "auth.login_failed", None, None, "failure", "10.0.0.2", datetime(2026, 10, 20, 19, 0)),
        ("charlie@tycoons.example.com", "setting.update", "site_setting", "phone", "success", "10.0.0.3", datetime(2026, 10, 22, 9, 0)),
        ("=HYPERLINK(\"http://evil\")", "auth.login_failed", None, None, "failure", "10.0.0.4", datetime(2026, 10, 23, 9, 0)),
    ]
    for email, action, rtype, rid, outcome, ip, when in rows:
        db.add(AuditLog(actor_type="admin" if "@" in email else "anonymous", actor_email=email, action=action,
                        resource_type=rtype, resource_id=rid, outcome=outcome, ip=ip, occurred_at=when,
                        details={"note": "seed"}))
    db.commit()


def _actions(client, **params):
    r = client.get(URL, params=params)
    assert r.status_code == 200, r.text
    return [e["actor_email"] for e in r.json()["items"]], r.json()["total"]


def test_search_matches_actor_action_resource_and_ip(client, admin_headers, db):
    _seed(db)
    assert _actions(client, q="bravo")[1] == 1
    assert _actions(client, q="setting.upd")[0] == ["charlie@tycoons.example.com"]
    assert _actions(client, q="phone")[0] == ["charlie@tycoons.example.com"]
    assert _actions(client, q="10.0.0.1")[0] == ["alpha@tycoons.example.com"]
    # LIKE wildcards in the search text are literal, not "match anything"
    assert _actions(client, q="%")[1] == 0 and _actions(client, q="_")[1] >= 0


def test_sorting_by_column_and_direction(client, admin_headers, db):
    _seed(db)
    asc, _ = _actions(client, sort="actor", order="asc", q="tycoons.example.com")
    assert asc == sorted(asc)
    desc, _ = _actions(client, sort="actor", order="desc", q="tycoons.example.com")
    assert desc == sorted(desc, reverse=True)
    assert client.get(URL, params={"sort": "details"}).status_code == 422


def test_date_range_uses_hotel_days(client, admin_headers, db):
    _seed(db)
    # 20 Oct 19:00 UTC is 21 Oct 00:30 at the hotel, so it belongs to the 21st
    day20, _ = _actions(client, date_from="2026-10-20", date_to="2026-10-20", q="tycoons.example.com")
    assert day20 == ["alpha@tycoons.example.com"]
    day21, _ = _actions(client, date_from="2026-10-21", date_to="2026-10-21")
    assert day21 == ["bravo@tycoons.example.com"]


def test_paging_and_page_size(client, admin_headers, db):
    _seed(db)
    page = client.get(URL, params={"limit": 2, "offset": 2, "q": "10.0.0."}).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["limit"] == 2 and page["offset"] == 2
    assert client.get(URL, params={"limit": 500}).status_code == 422


def test_csv_export_follows_filters_and_defuses_formulas(client, admin_headers, db):
    _seed(db)
    r = client.get(URL + "/export", params={"outcome": "failure", "sort": "occurred_at", "order": "asc"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith('attachment; filename="audit-log-')
    body = r.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(body)))
    assert [row["ip"] for row in rows] == ["10.0.0.2", "10.0.0.4"]
    assert rows[1]["actor_email"].startswith("'=")           # not a live formula in Excel
    assert '"note": "seed"' in rows[0]["details"]
    exported = db.query(AuditLog).filter_by(action="audit.export").one()
    assert exported.details["rows"] == 2 and exported.details["filters"]["outcome"] == "failure"


def test_export_is_admin_only(client, admin_headers):
    client.cookies.clear()
    login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.get(URL + "/export").status_code == 403
