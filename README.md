# The Tycoons Hotel — website

The hotel's website as a full-stack app: **React** (Vite) front end, **FastAPI** back end, **MySQL** database and **Razorpay** payments for room bookings.

The original single-file design, `the-tycoons-hotel.html`, is kept in the repo as the visual reference. The React site reproduces it pixel for pixel. All 8 pages were compared at 1440 px and 390 px wide with automated screenshots, and every pair matched exactly.

```
the-tycoons-hotel.html   original design (reference only)
frontend/                React 18 + React Router + GSAP (same animations as the original)
backend/                 FastAPI + SQLAlchemy 2 + Alembic + Razorpay SDK
deploy/                  nginx and systemd examples
scripts/                 portable MySQL helpers, dev launcher
```

## What the site does

| Area | Behaviour |
|---|---|
| Pages | Home, Rooms & Suites, Fishy Tales (dining), Kai Wellness Spa, Business Lounge, Gallery, Careers, Contact. Deep links such as `/dining#reserve` work, and old hash links (`/#rooms/book`) redirect. |
| Content from the DB | Room types and rates, spa treatments, menu, lounge and team cards, gallery photos, job openings, and site settings (address, phones, hours, detail strips, amenities ticker, map). |
| **Room booking + payment** | Check availability → choose a room → enter guest details → pay with Razorpay → confirmation page. Guests can look up a booking with its reference and email at `/booking/find`, and resume an interrupted payment while the room is still held. |
| Request forms | Table reservation, spa appointment, business enquiry, contact enquiry, job application (with CV upload) and newsletter. All are stored in the DB, validated on both client and server, and optionally emailed to the hotel. |
| Staff admin `/admin` | Dashboard, bookings (search, filter, detail, cancel with Razorpay refund, reconcile), payments, guest requests, rooms and rates, content, site settings, staff users, change password. |

Guests never sign in; only staff do. The design had no login, so none was added for guests.

### Placeholder content

The design's placeholders are seeded into the database **verbatim**, so the site looks exactly like the design until staff replace them in **Admin → Site settings / Rooms & rates / Content**. Examples: `[Street address]`, `[+91 Phone]`, `[Room size · sq ft]`, `[HOURS]`, `[Role title]`.

**Room rates and inventory are sample values** (the design has none): Twin ₹6,500 ×12 rooms, Premium ₹7,500 ×16, Deluxe ₹9,500 ×10, Tycoon Suite ₹16,000 ×2. **Set the real figures before taking bookings.** Room tax (GST) defaults to 0%; set it under *Site settings → Rooms & booking*.

---

## Local development (Windows)

Requirements: Python 3.12, Node 20+, Git. On this machine they were installed with winget. MySQL runs as a **portable MySQL 8.4** inside `.tools/`, on `127.0.0.1:3308`, so it doesn't touch any other MySQL on the machine.

### First-time setup

```powershell
# 1. Database (MySQL 8.4 "ZIP Archive" build unpacked to .tools\mysql)
.\scripts\mysql-init.ps1          # creates DBs tycoons + tycoons_test, user, writes backend\.env

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
# edit backend\.env: JWT_SECRET and the Razorpay test keys (see below)
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m app.cli seed
$env:ADMIN_PASSWORD = 'Choose-A-Strong-Pass1'
.\.venv\Scripts\python -m app.cli create-admin --email you@yourhotel.com --name "Your Name"
Remove-Item Env:ADMIN_PASSWORD

# 3. Frontend
cd ..\frontend
npm install
```

### Every day

```powershell
.\scripts\dev.ps1     # starts MySQL, the API (:8000) and the site (:5173)
```

| URL | |
|---|---|
| http://localhost:5173 | website |
| http://localhost:5173/admin | staff admin |
| http://localhost:8000/api/docs | Swagger UI (OpenAPI at `/api/openapi.json`, ReDoc at `/api/redoc`) |

Vite proxies `/api` and `/media` to FastAPI, so the browser sees a single origin, just as it will behind nginx.

Stop the database with `.\scripts\mysql-stop.ps1`.

### Environment variables

`backend/.env.example` documents every setting. The important ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://user:pass@host:port/tycoons?charset=utf8mb4` |
| `TEST_DATABASE_URL` | used only by pytest; its tables are dropped and recreated |
| `JWT_SECRET` | signs staff sessions. Use 32+ random characters (required in production) |
| `COOKIE_SECURE` | `true` behind HTTPS (required in production) |
| `CORS_ORIGINS` | comma-separated browser origins. Not needed when the site and API share an origin |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | API keys. Only the key **id** ever reaches the browser |
| `RAZORPAY_WEBHOOK_SECRET` | the secret you type when creating the webhook |
| `BOOKING_HOLD_MINUTES` | how long a room is held while the guest pays (default 15) |
| `HOTEL_TIMEZONE` | `Asia/Kolkata`. Booking dates are hotel-local; timestamps are stored in UTC |
| `SMTP_*`, `HOTEL_NOTIFY_EMAIL` | optional. Without `SMTP_HOST`, mail is written to the log instead of sent |
| `FRONTEND_DIST` | optional: let FastAPI serve the built site (otherwise nginx does) |

`frontend/.env.example`: `VITE_API_BASE_URL` (leave empty when same-origin).

---

## Razorpay

### Test mode

1. Razorpay Dashboard → switch to **Test Mode** → *Account & Settings → API Keys* → generate keys (`rzp_test_…`).
2. Put them in `backend/.env` as `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`, then restart the API.
3. *Account & Settings → Webhooks → Add*:
   - URL: `https://<your-domain>/api/payments/webhook`
   - Secret: any strong string, copied into `RAZORPAY_WEBHOOK_SECRET`
   - Events: `payment.captured`, `payment.failed`, `payment.authorized`, `order.paid`, `refund.processed`, `refund.failed`

   For webhooks to reach a local machine, expose port 8000 with a tunnel (for example ngrok or cloudflared). Payments still confirm without webhooks, through the checkout callback.
4. Keep **automatic capture** on (*Account & Settings → Payment capture*). If it is off, the API captures authorised payments itself.
5. Pay with Razorpay's test cards or UPI IDs, for example `success@razorpay` / `failure@razorpay`.

Without keys, the site still works; online booking replies *"Online payment is not available right now"* (HTTP 503).

### Going live

Generate **Live Mode** keys and a live webhook (same URL and events), replace the three values in the production `.env`, and restart. Nothing else changes.

### How payment status is decided

- The **server** computes the price from the database. Any amount sent by the browser is ignored.
- The booking holds a room for `BOOKING_HOLD_MINUTES`. The room-type row is locked while inventory is re-checked, so parallel checkouts cannot oversell. A test fires 6 simultaneous checkouts at a 2-room suite and exactly 2 succeed.
- A browser retry with the same `Idempotency-Key` returns the same booking and order. It never creates a second one.
- The checkout response is **untrusted**. `POST /api/payments/verify` checks the HMAC signature with the key secret, then fetches the payment from Razorpay and confirms the booking only if it is `captured` for the exact order, amount and currency.
- Webhooks are verified against the **raw request body** and deduplicated by `x-razorpay-event-id`. Replays are acknowledged and ignored.
- Statuses never move backwards: a late `payment.failed` cannot undo a capture.
- **Money arrives after the hold lapsed:** the booking is confirmed if a room is still free. Otherwise it is marked **payment_review**, and staff are notified so they can rehouse or refund.
- **Interrupted checkout:** the guest can resume on the same order while the hold lasts. Expired holds release the room automatically, both every minute and on lookup.
- **Reconciliation:** the *Reconcile* button in Admin → Bookings, or `python -m app.cli reconcile`, asks Razorpay what actually happened to unpaid orders. Run the CLI from cron every 10–15 minutes in production.
- No card data is stored: only order id, payment id, amount, currency, status, method, and error code/description.

---

## Tests

```powershell
cd backend;  .\.venv\Scripts\python -m pytest       # 76 tests, real MySQL (tycoons_test)
cd frontend; npm test                               # 10 tests (vitest + Testing Library)
```

Backend coverage:

- Public content, availability and pricing
- Booking holds, idempotency, overselling (including concurrency), expiry
- Payment verification: valid, invalid and mismatched signatures, amount mismatch, failed, authorised→capture, replay
- Webhooks: bad signature, tampered body, duplicates, `order.paid`, late failure after capture, capture after lapse, unknown orders
- Reconciliation and refunds
- All forms, including CV type sniffing and size limits
- Admin auth: cookies, CSRF, roles, logout revocation, last-admin protection, password policy
- Rate limiting
- The Alembic migration, which builds the test schema

Razorpay's network calls are faked; signature checks use the real SDK.

**Not automated:** a payment through the real Razorpay test environment, which needs your test keys (see *Remaining items*).

---

## Production deployment

1. **Server:** Ubuntu 22.04+ with Python 3.12, Node 20+ (build only), MySQL 8.4, nginx and certbot.
2. **Database:**
   ```sql
   CREATE DATABASE tycoons CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER 'tycoons'@'localhost' IDENTIFIED BY '<strong password>';
   GRANT ALL ON tycoons.* TO 'tycoons'@'localhost';
   ```
3. **Backend** (`/srv/tycoons/backend`): create the venv, `pip install -r requirements.txt`, write `.env` with `ENVIRONMENT=production`, `COOKIE_SECURE=true`, a fresh `JWT_SECRET` and the live Razorpay keys, then run `alembic upgrade head`, `python -m app.cli seed` and `python -m app.cli create-admin …`. Install `deploy/tycoons-api.service`. The app refuses to start in production without these secrets.
4. **Frontend:** run `npm ci && npm run build` and copy `frontend/dist` to `/srv/tycoons/frontend/dist`.
5. **nginx:** install `deploy/nginx.conf` (adjust the domain), then `certbot --nginx`. It serves the site, proxies `/api` and `/media`, falls back to `index.html` for client routes, and sends HSTS.
6. **Cron:** run `python -m app.cli reconcile` every 15 minutes, and back up MySQL plus `backend/storage/` daily (uploaded images; CVs live in `storage/private`, which is never web-served).

**Secrets:** keep `.env` files out of Git (they are in `.gitignore`), readable only by the service user. Prefer the host's secret store if one is available, and rotate the JWT secret and Razorpay keys if a server is ever compromised.

**Production notes:**

- The rate limiter keeps its counters in process memory, so run **one uvicorn worker** per host (as in the unit file) or move the limiter to Redis before scaling out.
- uvicorn trusts `X-Forwarded-For` only from nginx (`--forwarded-allow-ips`).

## API overview

All endpoints sit under `/api`; Swagger at `/api/docs` has every schema. Errors share one shape:

```json
{"error": {"code": "...", "message": "...", "details": [{"field": "...", "message": "..."}], "request_id": "..."}}
```

| Public | |
|---|---|
| `GET /site`, `/rooms`, `/spa/treatments`, `/content/cards?section=`, `/gallery?category=&home=&limit=&offset=`, `/careers/openings` | content |
| `GET /bookings/availability` | quote per room type for a stay |
| `POST /bookings` (`Idempotency-Key` header) | hold a room, create the Razorpay order |
| `POST /bookings/lookup`, `POST /bookings/{ref}/payment` | guest lookup, resume payment |
| `POST /payments/verify`, `/payments/report`, `/payments/webhook` | payment callbacks |
| `POST /dining/reservations`, `/spa/appointments`, `/enquiries/business`, `/enquiries/contact`, `/careers/applications`, `/newsletter` | forms |
| **Admin** (cookie session + `X-CSRF-Token`) | `/admin/auth/*`, `/admin/dashboard`, `/admin/bookings`, `/admin/payments`, `/admin/room-types`, `/admin/spa-treatments`, `/admin/content-cards`, `/admin/gallery`, `/admin/job-openings`, `/admin/settings`, `/admin/submissions/*`, `/admin/uploads/image`, `/admin/users` |

Roles: **admin** can do everything. **staff** can read bookings and payments and work guest requests. Every check is enforced in the API, not just hidden in the UI.

## Remaining items

- **Razorpay end-to-end in test mode has not been run:** no test keys were available. Signature verification, webhooks and every status transition are covered by automated tests against the real SDK verifier.
- Real hotel data must replace the placeholders, sample rates and inventory.
- Email confirmations need SMTP settings. Until then they are logged, not sent.
- Staff password reset is done by an administrator (*Staff users → Reset password*). There is no self-service "forgot password" email, because no mail server is configured.
- Terms & Conditions and Privacy Policy still link to Contact, as in the design. Pages for them need content from the hotel.
- The hero "film slot" from the design is kept: add a `<source>` to the `<video>` in `HeroSlideshow.jsx`.
