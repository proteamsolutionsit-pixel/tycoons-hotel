from app.models import Booking, Payment
from app.models.enums import BookingStatus, PaymentStatus
from tests.conftest import STAFF_PW, FakeGateway, create_booking, login


def test_admin_requires_authentication(client):
    for path in ("/api/v1/admin/auth/me", "/api/v1/admin/bookings", "/api/v1/admin/dashboard", "/api/v1/admin/settings"):
        assert client.get(path).status_code == 401


def test_login_failure_is_generic(client):
    r1 = client.post("/api/v1/admin/auth/login", json={"email": "admin@tycoons.example.com", "password": "wrong"})
    r2 = client.post("/api/v1/admin/auth/login", json={"email": "ghost@tycoons.example.com", "password": "wrong"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]


def test_login_sets_httponly_session_cookie(client):
    r = client.post("/api/v1/admin/auth/login", json={"email": "admin@tycoons.example.com", "password": "Admin-Password-123"})
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("tyc_admin="))
    csrf = next(c for c in cookies if c.startswith("tyc_csrf="))
    assert "httponly" in session.lower() and "httponly" not in csrf.lower()
    assert "samesite=lax" in session.lower()
    assert client.get("/api/v1/admin/auth/me").json()["role"] == "admin"


def test_state_change_requires_csrf_token(client, admin_headers):
    r = client.patch("/api/v1/admin/room-types/1", json={"base_rate_paise": 800000})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = client.patch("/api/v1/admin/room-types/1", json={"base_rate_paise": 800000}, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403
    assert client.patch("/api/v1/admin/room-types/1", json={"base_rate_paise": 800000},
                        headers=admin_headers).status_code == 200


def test_rate_change_is_used_for_new_quotes(client, admin_headers):
    client.patch("/api/v1/admin/room-types/2", json={"base_rate_paise": 820000}, headers=admin_headers)
    from tests.conftest import stay
    q = client.get("/api/v1/bookings/availability", params={**stay(nights=1), "adults": 2}).json()["rooms"]
    assert next(r for r in q if r["slug"] == "premium-room")["total_paise"] == 820000


def test_staff_cannot_change_rates_or_content(client):
    headers = login(client, "staff@tycoons.example.com", STAFF_PW)
    assert client.get("/api/v1/admin/bookings").status_code == 200  # can read
    for method, path, body in (("patch", "/api/v1/admin/room-types/1", {"base_rate_paise": 1}),
                               ("post", "/api/v1/admin/job-openings", {"title": "Chef", "department": "Kitchen",
                                                                   "employment_type": "Full-time"}),
                               ("put", "/api/v1/admin/settings/phone_display", {"value": "x"}),
                               ("get", "/api/v1/admin/users", None)):
        r = getattr(client, method)(path, json=body, headers=headers) if body else getattr(client, method)(path)
        assert r.status_code == 403, path


def test_logout_revokes_the_token(client, admin_headers):
    token = client.cookies.get("tyc_admin")
    assert client.post("/api/v1/admin/auth/logout", headers=admin_headers).status_code == 200
    client.cookies.set("tyc_admin", token, path="/api")
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_bookings_list_search_and_detail(client, gateway, admin_headers):
    ref = create_booking(client)["booking"]["reference"]
    create_booking(client, guest_email="other@example.com", guest_name="Other Guest")
    page = client.get("/api/v1/admin/bookings", params={"q": "asha"}).json()
    assert page["total"] == 1 and page["items"][0]["reference"] == ref
    detail = client.get(f"/api/v1/admin/bookings/{page['items'][0]['id']}").json()
    assert detail["payments"][0]["status"] == "created"
    assert client.get("/api/v1/admin/bookings", params={"status": "confirmed"}).json()["total"] == 0


def test_cancel_with_refund(client, gateway, admin_headers, db):
    res = create_booking(client)
    order_id = res["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    client.post("/api/v1/payments/verify", json={"razorpay_order_id": order_id, "razorpay_payment_id": pay["id"],
                                              "razorpay_signature": FakeGateway.sign(order_id, pay["id"])})
    bid = db.query(Booking).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel", json={"reason": "Guest request", "refund": True, "confirm_refund_paise": 1500000},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(Booking).one().status == BookingStatus.CANCELLED
    assert db.query(Payment).one().status == PaymentStatus.REFUNDED
    assert "refund_payment" in gateway.calls


def test_failed_refund_changes_nothing(client, gateway, admin_headers, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    pay = gateway.pay(order_id)
    client.post("/api/v1/payments/verify", json={"razorpay_order_id": order_id, "razorpay_payment_id": pay["id"],
                                              "razorpay_signature": FakeGateway.sign(order_id, pay["id"])})
    gateway.fail_refund = True
    bid = db.query(Booking).one().id
    r = client.post(f"/api/v1/admin/bookings/{bid}/cancel", json={"reason": "Guest request", "refund": True, "confirm_refund_paise": 1500000},
                    headers=admin_headers)
    assert r.status_code == 502
    db.expire_all()
    assert db.query(Booking).one().status == BookingStatus.CONFIRMED


def test_reconcile_applies_razorpay_state(client, gateway, admin_headers, db):
    order_id = create_booking(client)["checkout"]["order_id"]
    gateway.pay(order_id, status="failed")
    gateway.pay(order_id)  # a later attempt succeeded but no webhook/verify reached us
    pid = db.query(Payment).one().id
    r = client.post(f"/api/v1/admin/payments/{pid}/reconcile", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_submissions_list_and_update(client, admin_headers):
    client.post("/api/v1/enquiries/contact", json={"name": "Neha Shah", "email": "neha@acme.in", "topic": "Other",
                                                "message": "Hello there", "consent": True})
    page = client.get("/api/v1/admin/submissions/enquiries").json()
    assert page["total"] == 1
    item_id = page["items"][0]["id"]
    r = client.patch(f"/api/v1/admin/submissions/enquiries/{item_id}",
                     json={"status": "in_progress", "staff_notes": "Called back"}, headers=admin_headers)
    assert r.json()["status"] == "in_progress"
    assert client.get("/api/v1/admin/submissions/bogus").status_code == 404
    assert client.get("/api/v1/admin/dashboard").json()["new_submissions"]["enquiries"] == 0


def test_cv_download_is_admin_only(client, admin_headers):
    client.cookies.clear()
    client.post("/api/v1/careers/applications", data={
        "name": "Kiran Das", "email": "kiran@example.com", "phone": "9876543210", "position": "Chef",
        "consent": "true"}, files={"cv": ("cv.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert client.get("/api/v1/admin/submissions/applications/1/cv").status_code == 401
    login(client)
    r = client.get("/api/v1/admin/submissions/applications/1/cv")
    assert r.status_code == 200 and r.content == b"%PDF-1.4 test"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_settings_validation(client, admin_headers):
    ok = client.put("/api/v1/admin/settings/phone_display", json={"value": "+91 80 1234 5678"}, headers=admin_headers)
    assert ok.status_code == 200
    assert client.get("/api/v1/site").json()["settings"]["phone_display"] == "+91 80 1234 5678"
    assert client.put("/api/v1/admin/settings/stay_details", json={"value": ["not", "rows"]},
                      headers=admin_headers).status_code == 422
    assert client.put("/api/v1/admin/settings/room_tax_percent", json={"value": 150},
                      headers=admin_headers).status_code == 422
    assert client.put("/api/v1/admin/settings/instagram_url", json={"value": "javascript:alert(1)"},
                      headers=admin_headers).status_code == 422


def test_content_crud_and_image_url_validation(client, admin_headers):
    r = client.post("/api/v1/admin/job-openings", json={"title": "Sous Chef", "department": "Fishy Tales",
                                                     "employment_type": "Full-time"}, headers=admin_headers)
    assert r.status_code == 201
    assert any(o["title"] == "Sous Chef" for o in client.get("/api/v1/careers/openings").json())
    bad = client.post("/api/v1/admin/gallery", json={"image_url": "javascript:alert(1)", "alt": "x",
                                                  "category": "rooms"}, headers=admin_headers)
    assert bad.status_code == 422
    assert client.delete(f"/api/v1/admin/job-openings/{r.json()['id']}", headers=admin_headers).status_code == 204


def test_room_type_with_bookings_cannot_be_deleted(client, gateway, admin_headers):
    create_booking(client)
    r = client.delete("/api/v1/admin/room-types/2", headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "in_use"


def test_last_admin_is_protected(client, admin_headers):
    users = client.get("/api/v1/admin/users").json()
    me = next(u for u in users if u["role"] == "admin")
    r = client.patch(f"/api/v1/admin/users/{me['id']}", json={"role": "staff"}, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_admin"


def test_weak_password_rejected(client, admin_headers):
    r = client.post("/api/v1/admin/users", json={"email": "new@tycoons.example.com", "full_name": "New Person",
                                              "role": "staff", "password": "alllowercase1"}, headers=admin_headers)  # pragma: allowlist secret
    assert r.status_code == 400 and r.json()["error"]["code"] == "weak_password"


def test_image_upload_checks_content(client, admin_headers):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    ok = client.post("/api/v1/admin/uploads/image", files={"file": ("a.png", png, "image/png")}, headers=admin_headers)
    assert ok.status_code == 200 and ok.json()["url"].startswith("/media/images/")
    assert client.get(ok.json()["url"]).content == png
    bad = client.post("/api/v1/admin/uploads/image", files={"file": ("a.png", b"<svg onload=alert(1)>", "image/png")},
                      headers=admin_headers)
    assert bad.status_code == 400
    svg = client.post("/api/v1/admin/uploads/image", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")},
                      headers=admin_headers)
    assert svg.status_code == 400


def test_login_rate_limited(client, settings):
    from app.core.rate_limit import limiter
    settings.rate_limit_enabled = True
    limiter.reset()
    try:
        codes = [client.post("/api/v1/admin/auth/login", json={"email": "admin@tycoons.example.com", "password": "x"}).status_code
                 for _ in range(6)]
    finally:
        settings.rate_limit_enabled = False
    assert codes[:5] == [401] * 5 and codes[5] == 429
