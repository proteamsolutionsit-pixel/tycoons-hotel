# Security & architecture audit — The Tycoons Hotel

Date: 2026-10-23 · Scope: `backend/` (FastAPI, SQLAlchemy, Alembic, Razorpay), `frontend/` (React), MySQL schema, deployment files.
No production data was involved: the only database is the local development copy, which was backed up first
(`scripts/mysql-backup.ps1` → `backups/tycoons-20261023T072408Z.sql`).

## 1. Current implementation (as audited)

| Layer | What exists |
|---|---|
| API | ~70 endpoints under `/api` (unversioned): public content, availability, bookings, payments, 6 forms, staff admin. Pydantic v2 schemas, one error envelope `{"error": {code, message, details, request_id}}`. |
| Services | `booking_service` (holds, idempotency, Razorpay orders), `payment_service` (verify, webhooks, reconcile, refunds), `availability`, `upload_service`, `mailer`. |
| Data | 15 tables, Alembic migration `8f2012434e2d`. Money in integer paise. Bookings hold inventory with a `SELECT … FOR UPDATE` on the room type. |
| Auth | Guests: none (booking = reference + email). Staff: bcrypt password → JWT in HttpOnly cookie (8 h) + double-submit CSRF cookie; roles `admin` / `staff`. |
| Payments | Server-side order creation, SDK HMAC verification, payment fetched from Razorpay before confirming, webhook HMAC on raw body, dedupe by `x-razorpay-event-id`, monotonic statuses, reconciliation CLI/button. |
| Tests | 76 backend (real MySQL) + 10 frontend, all passing before any change. |

Verified as **sound** and kept: server-side pricing (client amounts ignored), row-lock inventory (concurrency test: 6
parallel checkouts on a 2-room suite → exactly 2 holds), idempotency keys, signature checks, webhook dedupe, no card
data stored, uploads sniffed by magic bytes with random names, CVs outside any web root.

## 2. Findings

Severity: **C** critical · **H** high · **M** medium · **L** low. "Evidence" is how the finding was established.

### Security

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| S1 | C | Vulnerable dependencies: starlette 0.46.2 (7 advisories incl. request-parsing DoS), PyJWT 2.10.1 (17), setuptools 80.9 (1); react-router 6.28 (open redirect via backslash, SSR injection), vite/esbuild dev-server read, vitest/tinypool RCE gadgets. | `pip-audit` 26 findings, `npm audit` 8 findings |
| S2 | H | Staff sessions are stateless JWTs: fixed 8 h life, **no idle timeout**, a single session cannot be revoked (only "all", via `token_version`), CSRF token not bound to the session. | `core/security.py`, `api/deps.py` |
| S3 | H | Passwords hashed with bcrypt rather than Argon2id; no common-password check; no self-service reset (admin-only). | `core/security.py` |
| S4 | H | **No audit trail** for rate changes, refunds, cancellations, role/user changes, settings; auth failures only in the text log. | code review |
| S5 | H | Rate limiter keeps counters in process memory → bypassed by running >1 worker/instance; deploy file pinned to 1 worker as a workaround. | `core/rate_limit.py`, `deploy/tycoons-api.service` |
| S6 | H | Full Razorpay webhook bodies stored in `payment_events.payload` — includes customer email, phone, VPA, bank/card network data. | `payment_service.handle_webhook` |
| S7 | H | Runtime DB account has `ALL PRIVILEGES` (DROP/ALTER) — the app needs only DML; no option for TLS to MySQL. | `scripts/mysql-init.ps1` |
| S8 | M | `.env.example` puts comments on value lines; systemd `EnvironmentFile` (used by the deploy unit) keeps them as part of the value → `ENVIRONMENT="production   # …"` fails validation. | inspected `.env` parsing |
| S9 | M | No `TrustedHost` check, no request-body size cap (multipart parsed before handlers can reject), HSTS left entirely to nginx. | `main.py` |
| S10 | M | Refund issued on any captured payment with no eligibility rules or amount confirmation; refunds made in the Razorpay dashboard leave the booking "confirmed" with no alert. | `payment_service.cancel_booking`, webhook handler |
| S11 | M | Booking lookup throttled per IP only (distributed guessing of reference+email not limited per booking). | `routes/bookings.py` |
| S12 | M | `map_embed_url` is validated only in the browser; the API accepts any https URL into an iframe. | `admin/content.py`, `Contact.jsx` |
| S13 | L | No log redaction safety net (any future `log.info(payload)` would write secrets/PII). | `core/logging.py` |

### Booking & payment correctness

| ID | Sev | Finding |
|---|---|---|
| B1 | H | Booking/payment status changes are assigned ad hoc in several functions; no single definition of legal transitions. |
| B2 | H | The guest's acceptance of terms is validated but **not recorded** (no version, timestamp or cancellation-policy snapshot on the booking). |
| B3 | M | `refund.processed` for a refund created outside the app does not flag the still-confirmed booking (see S10). |
| B4 | L | Availability search runs one query per room type; admin bookings list lazy-loads payments per row (N+1). |

### Architecture & API

| ID | Sev | Finding |
|---|---|---|
| A1 | M | No API version prefix; the Razorpay webhook URL is bound to the current path. |
| A2 | M | Business logic in route handlers (`routes/forms.py` persistence + notifications; settings validation in `admin/content.py`; user rules in `admin/users.py`); `job_application` (async) does blocking DB I/O on the event loop. |
| A3 | L | Submissions list returns untyped dicts → OpenAPI shows no schema. |
| A4 | L | One health endpoint (does a DB query); no liveness/readiness split; engine not disposed on shutdown. |
| A5 | L | No lint / type / vulnerability / secret scanning, no CI. Deprecations: Alembic `path_separator`. |

### Admin UI

| ID | Finding |
|---|---|
| U1 | No top bar, no icons, no responsive navigation drawer. |
| U2 | Tables cannot be sorted; no reservation calendar / occupancy view; dashboard lacks occupancy. |
| U3 | Destructive and financial actions use `window.confirm` (no amount summary, not styled, poor accessibility). |
| U4 | No audit-log view, no "forgot password", no toast feedback, minimal empty/error states. |

## 3. Remediation plan (executed in this order)

| # | Work | Files | DB change | Compatibility |
|---|---|---|---|---|
| 1 | Upgrade dependencies to patched releases; remove PyJWT | `requirements*.txt`, `package.json` | – | React Router 6→7 (future flags were already on) |
| 2 | Server-side staff sessions (idle 30 min, absolute 12 h, per-session revoke, CSRF bound to session); Argon2id with transparent bcrypt upgrade on login; common-password denylist; email password reset (hashed single-use 30-min tokens) | `core/security.py`, `services/auth_service.py`, `api/deps.py`, `routes/admin/auth.py` | `admin_sessions`, `password_reset_tokens` | existing staff passwords keep working; everyone signs in once more |
| 3 | Permission-based RBAC (`admin`, `staff` mapped to permissions); every admin route declares its permission; test enumerates all routes | `core/permissions.py`, admin routes | – | same effective rights as before |
| 4 | Append-only audit log (+ DB triggers rejecting UPDATE/DELETE) for admin actions and security events; admin viewer | `services/audit.py`, `models/audit.py` | `audit_logs` + triggers | – |
| 5 | Shared rate limiter in MySQL (works across workers/hosts), memory backend for tests | `core/rate_limit.py` | `rate_limit_buckets` | 429 + `Retry-After` unchanged |
| 6 | Booking/payment state machine; record terms version, acceptance time and cancellation-policy snapshot; refund eligibility + amount confirmation; flag external refunds; redact stored webhook payloads; per-reference lookup limit | `domain/states.py`, services, schemas | `bookings` +3 columns | `accept_terms` request unchanged |
| 7 | `/api/v1` with `/api` kept as a hidden, deprecated alias (incl. webhook); TrustedHost, body-size limit, HSTS in production, log redaction, live/ready health, graceful shutdown, DB pool/timeouts/TLS options | `main.py`, `middleware/`, `core/` | – | old URLs keep working |
| 8 | Move business logic out of routes (forms, settings, users), typed responses, N+1 fixes, single-query availability, sortable admin lists, occupancy calendar & dashboard occupancy/alerts | services, repositories, routes | indexes for reports | additive |
| 9 | Restricted runtime DB user (DML only; audit table insert/select only) separate from the migration user | `scripts/mysql-grant-app-user.ps1`, settings | grants only | `MIGRATION_DATABASE_URL` added |
| 10 | Admin UI: sidebar + top bar with icons, responsive drawer, sortable tables, calendar, accessible confirm dialogs, toasts, audit log, forgot/reset password | `frontend/src/admin/**` | – | public site untouched |
| 11 | Tests for all of the above, ruff/mypy/pip-audit/npm audit/detect-secrets, CI workflow; re-run visual regression of the public site | `tests/`, `scripts/check.ps1`, `.github/workflows/ci.yml` | – | – |

**Migration safety.** All schema changes are additive (new tables, new nullable columns, new indexes, triggers).
Nothing is dropped or rewritten. The migration has a tested `downgrade()`. Procedure: back up → `alembic upgrade head`
→ verify → (rollback: `alembic downgrade -1` and/or restore the dump).

**Not in scope / needs a decision.** Seasonal rates, discounts and fees do not exist in the application, so none were
added. Guest accounts do not exist (guests use reference + email); no "customer" role was invented. A real Razorpay
test-mode run requires the hotel's test keys.
