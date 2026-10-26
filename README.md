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
.\scripts\mysql-init.ps1          # creates DBs tycoons + tycoons_test and the schema owner, writes backend\.env

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
# edit backend\.env: the Razorpay test keys (see below)
.\.venv\Scripts\alembic upgrade head           # runs as the schema owner
..\scripts\mysql-grant-app-user.ps1            # DML-only runtime account; points DATABASE_URL at it
.\.venv\Scripts\python -m app.cli seed
$env:ADMIN_PASSWORD = 'Choose-A-Strong-Pass1'  # pragma: allowlist secret
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
| http://localhost:8000/api/v1/docs | Swagger UI (OpenAPI at `/api/v1/openapi.json`, ReDoc at `/api/v1/redoc`) - development only; switched off on staging/production |

Vite proxies `/api` and `/media` to FastAPI, so the browser sees a single origin, just as it will behind nginx.

Stop the database with `.\scripts\mysql-stop.ps1`.

### Environment variables

`backend/.env.example` documents every setting. The important ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | runtime account, DML only: `mysql+pymysql://tycoons_app:…@host:port/tycoons?charset=utf8mb4` |
| `MIGRATION_DATABASE_URL` | schema owner, used only by Alembic |
| `TEST_DATABASE_URL` | used only by pytest; its tables are dropped and recreated |
| `DATABASE_SSL_CA` | CA bundle path: requires TLS to MySQL (use when the DB is on another host) |
| `ALLOWED_HOSTS` | Host headers the API answers to (production: your domain) |
| `PUBLIC_BASE_URL` | public https URL, used in password-reset emails |
| `SESSION_IDLE_MINUTES` / `SESSION_ABSOLUTE_HOURS` | staff session limits (30 min / 12 h) |
| `COOKIE_SECURE` | `true` behind HTTPS (required in production) |
| `RATE_LIMIT_BACKEND` | `database` (shared across workers; required in production) or `memory` |
| `CORS_ORIGINS` | comma-separated browser origins. Not needed when the site and API share an origin |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | API keys. Only the key **id** ever reaches the browser |
| `RAZORPAY_WEBHOOK_SECRET` | the secret you type when creating the webhook |
| `SETTINGS_ENCRYPTION_KEY` | optional Fernet key for secrets entered in *Admin → Payment gateway*; otherwise a key file is created under `STORAGE_DIR/private/` |
| `BOOKING_HOLD_MINUTES` | how long a room is held while the guest pays (default 15) |
| `HOTEL_TIMEZONE` | `Asia/Kolkata`. Booking dates are hotel-local; timestamps are stored in UTC |
| `SMTP_*`, `HOTEL_NOTIFY_EMAIL` | optional. Without `SMTP_HOST`, mail is written to the log instead of sent |
| `FRONTEND_DIST` | optional: let FastAPI serve the built site (otherwise nginx does) |

`frontend/.env.example`: `VITE_API_BASE_URL` (leave empty when same-origin).

---

## Staff roles & access

*Admin → Roles & access* (Administrator only) defines roles and the permissions each one grants, grouped as Operations, Property and Administration; *Admin → Staff users* gives each user one role.

- **Administrator** (built-in) always has every permission, including roles and payment keys; it can't be edited or deleted, and the last active administrator can't be removed or demoted.
- **Front desk** (built-in) starts with the original staff access; it can be edited but not deleted.
- Ticking an action also grants what it needs to see (e.g. *Issue refunds* brings *View payments*, *View bookings* and *Manage bookings*).
- Permissions are read on every request, so a role change applies at once; menu items the role doesn't allow are hidden and the API refuses them (403, logged).
- No privilege escalation: someone who manages staff can assign only roles within their own access, and can't edit, deactivate or reset the password of a user with more access. Defining roles (`roles.manage`) can never be granted to a custom role.
- Every role and user change is in the audit log (`role.create/update/delete`, with permissions added/removed).

## Razorpay

### From the admin (recommended)

*Admin → Payment gateway* (admin role only) sets the payment mode and the Razorpay keys without editing files or restarting anything:

- choose **Razorpay** or **Test payments without Razorpay** (the latter is unavailable in production);
- paste the Key Id and Key Secret, press **Generate** for a webhook secret, and copy the webhook URL shown into Razorpay;
- **Test connection** makes one read-only call to Razorpay with the keys; **Save** applies them to the next request.

Secrets are encrypted at rest (Fernet; key from `SETTINGS_ENCRYPTION_KEY` or `STORAGE_DIR/private/settings.key`, never the database), are never sent back to the browser, and every change and connection test is in the audit log (which records the key id and *whether* a secret changed, never the secret). Switching to `rzp_live_` keys asks for an explicit confirmation. **Use server configuration** deletes the saved settings so `backend/.env` applies again.

If the encryption key is lost or changed, saved secrets can't be decrypted: payments switch off (they never fall back to anything else) and the page asks for the keys again.

The steps below do the same through `backend/.env`.

### Test mode

1. Razorpay Dashboard → switch to **Test Mode** → *Account & Settings → API Keys* → generate keys (`rzp_test_…`).
2. Put them in `backend/.env` as `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`, then restart the API.
3. *Account & Settings → Webhooks → Add*:
   - URL: `https://<your-domain>/api/v1/payments/webhook` (the pre-1.1 URL `/api/payments/webhook` still works)
   - Secret: any strong string, copied into `RAZORPAY_WEBHOOK_SECRET`
   - Events: `payment.captured`, `payment.failed`, `payment.authorized`, `order.paid`, `refund.processed`, `refund.failed`

   For webhooks to reach a local machine, expose port 8000 with a tunnel (for example ngrok or cloudflared). Payments still confirm without webhooks, through the checkout callback.
4. Keep **automatic capture** on (*Account & Settings → Payment capture*). If it is off, the API captures authorised payments itself.
5. Pay with Razorpay's test cards or UPI IDs, for example `success@razorpay` / `failure@razorpay`.

Without keys, the site still works; online booking replies *"Online payment is not available right now"* (HTTP 503).

### Without a Razorpay account: test payment mode

Set `PAYMENT_MODE=mock` in `backend/.env` and restart the API. Bookings then work end to end with no Razorpay account and no money: at checkout the site shows a **"Test mode · no real payment"** window with *Pay (test)*, *Simulate failed payment* and *Cancel*.

Everything except the call to Razorpay's servers is the real code path: server-side price, room hold, HMAC signature verification, the payment state machine, admin refunds and reconcile, and the audit log. Test payments appear in the admin with method `test` and ids starting `order_mock` / `pay_mock`.

**Production refuses to start with `PAYMENT_MODE=mock`.** Switch back to `PAYMENT_MODE=razorpay` once real keys are in place.

### Going live

Generate **Live Mode** keys and a live webhook (same URL and events), replace the three values in the production `.env`, and restart. Nothing else changes.

### How payment status is decided

- The **server** computes the price from the database. Any amount sent by the browser is ignored.
- The booking holds a room for `BOOKING_HOLD_MINUTES`. The room-type row is locked while inventory is re-checked, so parallel checkouts cannot oversell. A test fires 6 simultaneous checkouts at a 2-room suite and exactly 2 succeed.
- A browser retry with the same `Idempotency-Key` returns the same booking and order. It never creates a second one.
- The checkout response is **untrusted**. `POST /api/v1/payments/verify` checks the HMAC signature with the key secret, then fetches the payment from Razorpay and confirms the booking only if it is `captured` for the exact order, amount and currency.
- Webhooks are verified against the **raw request body** and deduplicated by `x-razorpay-event-id`. Replays are acknowledged and ignored.
- Statuses never move backwards: a late `payment.failed` cannot undo a capture.
- **Money arrives after the hold lapsed:** the booking is confirmed if a room is still free. Otherwise it is marked **payment_review**, and staff are notified so they can rehouse or refund.
- **Interrupted checkout:** the guest can resume on the same order while the hold lasts. Expired holds release the room automatically, both every minute and on lookup.
- **Reconciliation:** the *Reconcile* button in Admin → Bookings, or `python -m app.cli reconcile`, asks Razorpay what actually happened to unpaid orders. Run the CLI from cron every 10–15 minutes in production.
- No card data is stored: only order id, payment id, amount, currency, status, method, and error code/description.

---

## Tests and quality gates

```powershell
.\scripts\check.ps1     # everything CI runs; exit code = number of failed gates
```

| Gate | Result at release (2026-10-23) |
|---|---|
| ruff (lint + bandit security rules) | all checks passed |
| mypy (types) | no issues in 67 source files |
| pytest, real MySQL (`tycoons_test`) | **261 passed** |
| pip-audit (runtime + dev) | no known vulnerabilities |
| detect-secrets | clean (audited false positives are marked inline with `pragma: allowlist secret`) |
| npm audit | 0 vulnerabilities |
| vitest | **15 passed** |
| vite build | ok |

Backend coverage includes:

- Pricing, availability, holds, idempotency, overselling (6 parallel checkouts on a 2-room suite → exactly 2), expiry
- Payment verification: valid, invalid and mismatched signatures, amount mismatch, failed, authorised→capture, replay
- Webhooks: bad signature, tampered body, duplicates, `order.paid`, late failure after capture, capture after lapse, unknown orders, external refunds, payload redaction
- Refunds: amount confirmation, permission, no double refund, nothing-to-refund, failed refund changes nothing
- Auth: Argon2id, bcrypt upgrade, idle/absolute expiry, per-session logout, CSRF bound to session, password reset, policy
- Authorisation: generated from the live route table: every admin route declares a permission, refuses anonymous callers, and refuses staff outside their role
- Audit log: written with each change, rolled back with failed changes, append-only in the database
- Platform: `/api/v1` and legacy aliases, body-size limits, trusted hosts, error envelopes without internals, health, shared rate limiter, state machine, dashboard figures, migration downgrade/upgrade round trip

Also verified in a real browser (Microsoft Edge via Playwright, not committed):

- **Public site is still pixel-identical** to `the-tycoons-hotel.html` on all 8 pages at 1440 px and 390 px.
- End-to-end: forms, booking search, admin sign-in and audit trail, mobile admin navigation, no console errors.
- **The production CSP** (`deploy/csp.txt`) loads every public and admin page with **0 violations**.

**Not run:** a payment through Razorpay's test environment, because no test keys were provided (see *Remaining items*).

---

## Production deployment

Step-by-step deploy, migration, rollback, backup and monitoring procedures are in **[docs/OPERATIONS.md](docs/OPERATIONS.md)**. The controls are described in **[docs/SECURITY.md](docs/SECURITY.md)**, and the audit that led to them in **[docs/AUDIT.md](docs/AUDIT.md)**.

In short:

1. **Server:** Ubuntu 22.04+ with Python 3.12, Node 20+ (build only), MySQL 8.4, nginx and certbot.
2. **Database:** two accounts. The schema owner (`tycoons`, all rights on `tycoons.*`) is used only by Alembic. The runtime account (`tycoons_app`) gets DML per table and only `SELECT, INSERT` on `audit_logs`; the statements are in `scripts/mysql-grant-app-user.ps1`. Use `DATABASE_SSL_CA` if MySQL is on another host.
3. **Backend:** create the venv and run `pip install -r requirements.txt`. Write `.env` with one `KEY=value` per line and comments on their own lines. Set at least `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `ALLOWED_HOSTS`, `PUBLIC_BASE_URL=https://…` and the live Razorpay keys. The app refuses to start in production with unsafe settings. Then run `alembic upgrade head` as the owner, apply the grants, run `python -m app.cli seed` and `python -m app.cli create-admin …`, and install `deploy/tycoons-api.service` (2 workers, hardened unit).
4. **Frontend:** `npm ci && npm run build`, then copy `frontend/dist` to `/srv/tycoons/frontend/dist`.
5. **nginx:** `deploy/nginx.conf` sets HTTPS only, HSTS, the CSP, a host allowlist and the SPA fallback, and limits readiness checks to localhost.
6. **Cron:** `python -m app.cli reconcile` every 15 minutes; nightly backups of MySQL and `backend/storage/`.

## API overview

All endpoints are under **`/api/v1`**. Swagger at `/api/v1/docs` documents every schema. The pre-1.1 paths under `/api/...` still work but are hidden from the docs and answer with a `Deprecation: true` header.

Errors share one shape. 4xx errors are business or validation problems, safe to show to users; 5xx errors are server faults and never contain internals:

```json
{"error": {"code": "...", "message": "...", "details": [{"field": "...", "message": "..."}], "request_id": "..."}}
```

Conventions: money is integer paise (INR); stay dates are hotel-local `YYYY-MM-DD` (Asia/Kolkata); timestamps are UTC ISO-8601; lists return `{items, total, limit, offset}`.

| Public | |
|---|---|
| `GET /health/live`, `/health/ready` | liveness, readiness (DB + schema version) |
| `GET /site`, `/rooms`, `/spa/treatments`, `/content/cards?section=`, `/gallery?category=&home=&limit=&offset=`, `/careers/openings` | content |
| `GET /bookings/availability` | quote per room type for a stay |
| `POST /bookings` (`Idempotency-Key` header) | hold a room, create the Razorpay order |
| `POST /bookings/lookup`, `POST /bookings/{ref}/payment` | guest lookup, resume payment |
| `POST /payments/verify`, `/payments/report`, `/payments/webhook` | payment callbacks |
| `POST /dining/reservations`, `/spa/appointments`, `/enquiries/business`, `/enquiries/contact`, `/careers/applications`, `/newsletter` | forms |
| **Admin** (session cookie + `X-CSRF-Token`) | `/admin/auth/*` (login, logout, me, change-password, password-reset), `/admin/dashboard`, `/admin/occupancy`, `/admin/bookings` (+ cancel, confirm), `/admin/payments` (+ reconcile), `/admin/room-types`, `/admin/spa-treatments`, `/admin/content-cards`, `/admin/gallery`, `/admin/job-openings`, `/admin/settings`, `/admin/submissions/*`, `/admin/uploads/image`, `/admin/users`, `/admin/audit-logs` |

Roles and permissions are listed in [docs/SECURITY.md](docs/SECURITY.md#roles).

## Remaining items

- **Razorpay test mode end-to-end has not been run:** no test keys were available. Signature verification uses the real SDK, and every payment state transition is tested with a simulated gateway. Run one successful, one failed and one refunded test payment before going live.
- **No independent security review yet.** The tests and scanners are evidence, not a guarantee; commission a penetration test before launch.
- No MFA for staff (recommended next step: TOTP); guests use reference + email rather than accounts.
- Real hotel data must replace the placeholders, sample rates and inventory. Set the **cancellation policy** in Site settings; it is shown at checkout and saved with each booking.
- Emails (confirmations, password-reset links) need SMTP settings; until then they go to the application log.
- Terms & Conditions and Privacy Policy still link to Contact, as in the design.
- The hero "film slot" from the design is kept: add a `<source>` to the `<video>` in `HeroSlideshow.jsx`.
