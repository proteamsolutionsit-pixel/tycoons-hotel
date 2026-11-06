"""Site settings: several landline numbers, each with a label."""
from app.models import AuditLog, SiteSetting

URL = "/api/v1/admin/settings/landline_numbers"


def test_landline_setting_is_seeded_with_one_placeholder_row(client, db):
    row = db.get(SiteSetting, "landline_numbers")
    assert row is not None and row.group == "contact"
    assert row.value == [{"label": "Reception", "value": "[Landline number]"}]


def test_admin_saves_several_numbers_and_the_site_gets_them(client, admin_headers, db):
    numbers = [{"label": "Reception", "value": "080 4123 4567"},
               {"label": "Front office", "value": "+91 80 4123 4568"},
               {"label": "Banquets", "value": "(080) 4123-4569"}]
    r = client.put(URL, json={"value": numbers}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/site").json()["settings"]["landline_numbers"] == numbers
    assert db.query(AuditLog).filter_by(action="setting.update", resource_id="landline_numbers").count() == 1


def test_all_numbers_can_be_removed(client, admin_headers):
    assert client.put(URL, json={"value": []}, headers=admin_headers).status_code == 200


def test_invalid_numbers_are_refused(client, admin_headers):
    bad = [
        [{"label": "Reception", "value": "call us"}],                       # not a number
        [{"label": "", "value": "080 4123 4567"}],                          # no label
        [{"label": "Reception", "value": "080 4123 4567", "x": "y"}],       # unexpected field
        [{"label": f"L{i}", "value": "080 4123 4567"} for i in range(11)],  # too many
        "080 4123 4567",                                                    # not a list
    ]
    for value in bad:
        r = client.put(URL, json={"value": value}, headers=admin_headers)
        assert r.status_code == 422, (value, r.text)


def test_staff_cannot_change_numbers(client):
    from tests.conftest import STAFF_PW, login
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.put(URL, json={"value": []}, headers=headers).status_code == 403
