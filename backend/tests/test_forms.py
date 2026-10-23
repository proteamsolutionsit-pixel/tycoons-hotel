from datetime import timedelta

from app.core.timeutil import hotel_today
from app.models import Enquiry, JobApplication, NewsletterSubscriber, SpaAppointment, TableReservation
from app.services.upload_service import resolve_private

FUTURE = (hotel_today() + timedelta(days=5)).isoformat()


def test_table_reservation(client, db):
    r = client.post("/api/v1/dining/reservations", json={
        "name": "Ravi Kumar", "phone": "+91 99000 11111", "date": FUTURE, "time": "20:00", "guests": "5-8",
        "occasion": "Birthday", "requests": "Window seat"})
    assert r.status_code == 201
    row = db.query(TableReservation).one()
    assert row.party_size == "5-8" and row.status.value == "new"


def test_table_reservation_validation(client):
    past = (hotel_today() - timedelta(days=1)).isoformat()
    r = client.post("/api/v1/dining/reservations", json={
        "name": "R", "phone": "abc", "date": FUTURE, "time": "20:00", "guests": "7"})
    assert r.status_code == 422
    assert {d["field"] for d in r.json()["error"]["details"]} >= {"name", "phone", "guests"}
    r = client.post("/api/v1/dining/reservations", json={
        "name": "Ravi Kumar", "phone": "9900011111", "date": past, "time": "20:00", "guests": "2"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "date"


def test_spa_appointment_with_and_without_treatment(client, db):
    tid = client.get("/api/v1/spa/treatments").json()[0]["id"]
    base = {"name": "Meera Iyer", "phone": "9845012345", "guest_type": "visitor", "date": FUTURE, "time": "11:30"}
    assert client.post("/api/v1/spa/appointments", json={**base, "treatment_id": tid}).status_code == 201
    assert client.post("/api/v1/spa/appointments", json=base).status_code == 201  # "Not sure - advise me"
    assert client.post("/api/v1/spa/appointments", json={**base, "treatment_id": 9999}).status_code == 422
    assert db.query(SpaAppointment).count() == 2


def test_business_enquiry(client, db):
    r = client.post("/api/v1/enquiries/business", json={
        "company": "Acme Pvt Ltd", "name": "Neha Shah", "email": "neha@acme.in", "phone": "+91 80 4000 1234",
        "date": FUTURE, "attendees": 12, "requirements": "Rooms for 12 and a client dinner"})
    assert r.status_code == 201
    assert db.query(Enquiry).one().kind.value == "business"


def test_contact_enquiry_requires_consent(client, db):
    body = {"name": "Neha Shah", "email": "neha@acme.in", "topic": "Fishy Tales", "message": "Do you host events?"}
    r = client.post("/api/v1/enquiries/contact", json={**body, "consent": False})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "consent"
    assert client.post("/api/v1/enquiries/contact", json={**body, "consent": True}).status_code == 201
    assert client.post("/api/v1/enquiries/contact", json={**body, "topic": "Hacking", "consent": True}).status_code == 422


def test_newsletter_is_idempotent(client, db):
    for _ in range(2):
        r = client.post("/api/v1/newsletter", json={"email": "Fan@Example.com", "consent": True})
        assert r.status_code == 201
    assert db.query(NewsletterSubscriber).one().email == "fan@example.com"
    assert client.post("/api/v1/newsletter", json={"email": "x@example.com", "consent": False}).status_code == 422


def _apply(client, files=None, **over):
    data = {"name": "Kiran Das", "email": "kiran@example.com", "phone": "9876543210",
            "position": "Front office associate", "message": "Hello", "consent": "true", **over}
    return client.post("/api/v1/careers/applications", data=data, files=files)


def test_job_application_with_pdf(client, db):
    pdf = b"%PDF-1.7\n" + b"0" * 2048
    r = _apply(client, files={"cv": ("My CV.pdf", pdf, "application/pdf")})
    assert r.status_code == 201
    row = db.query(JobApplication).one()
    assert row.cv_original_name == "My CV.pdf" and row.cv_size == len(pdf)
    assert row.cv_path.startswith("cv/") and not row.cv_path.endswith("My CV.pdf")  # random stored name
    assert resolve_private(row.cv_path).read_bytes() == pdf


def test_job_application_without_cv_and_consent_rules(client, db):
    assert _apply(client).status_code == 201
    r = _apply(client, consent="false", email="bad")
    assert r.status_code == 422
    assert {d["field"] for d in r.json()["error"]["details"]} == {"consent", "email"}


def test_job_application_rejects_disguised_and_oversized_files(client, db, settings):
    exe = b"MZ\x90\x00" + b"\x00" * 100
    r = _apply(client, files={"cv": ("cv.pdf", exe, "application/pdf")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_file_content"
    r = _apply(client, files={"cv": ("cv.php", b"<?php echo 1;", "application/pdf")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_file_type"
    big = b"%PDF-" + b"0" * (settings.max_cv_bytes + 10)
    r = _apply(client, files={"cv": ("cv.pdf", big, "application/pdf")})
    assert r.status_code == 413
    assert db.query(JobApplication).count() == 0


def test_rate_limit_on_forms(client, settings):
    from app.core.rate_limit import limiter
    settings.rate_limit_enabled = True
    limiter.reset()
    try:
        codes = [client.post("/api/v1/newsletter", json={"email": f"u{i}@example.com", "consent": True}).status_code
                 for i in range(10)]
    finally:
        settings.rate_limit_enabled = False
    assert codes[:8] == [201] * 8 and codes[8] == 429
