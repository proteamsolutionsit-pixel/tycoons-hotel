# Security overview — The Tycoons Hotel

How the application protects guests, payments and staff accounts, and how each control is verified. This describes the
code as of migration `e52a1c1bd47a`. It is **not** a substitute for an independent penetration test (see *Limits* at the end).

## Architecture in one paragraph

React SPA and FastAPI share one origin behind nginx. Guests never sign in; a booking is reached with its reference plus
the email used to make it. Staff sign in to `/admin`. Every admin permission is enforced in the API; the UI only hides what
a role cannot use. MySQL holds all state, accessed through a DML-only account. Razorpay holds all card data.

## Controls

| Area | Control | Where | Verified by |
|---|---|---|---|
| **Staff passwords** | Argon2id (RFC 9106 low-memory profile); legacy bcrypt hashes verified and upgraded on next sign-in; 12–128 chars, mixed case + digit, no common words / hotel name / own name or email | `core/security.py` | `test_auth_sessions.py` |
| **Sessions** | Opaque 256-bit token in an HttpOnly, SameSite=Lax (Secure in prod) cookie scoped to `/api`; only its SHA-256 stored; 30 min idle and 12 h absolute expiry; revoked on logout, password change/reset, role change, deactivation | `services/auth_service.py`, `models/security.py` | idle, absolute, logout, revocation tests |
| **CSRF** | Per-session token: readable cookie echoed in `X-CSRF-Token`; server compares its hash with the one bound to the session, so a token from another session fails | `api/deps.py` | `test_csrf_token_is_bound_to_its_session` |
| **Password reset** | Single-use 256-bit token, 30 min, hashed at rest, link uses a URL *fragment* (not logged / not sent as Referer); identical reply for unknown emails; revokes all sessions | `auth_service` | `test_password_reset_flow` |
| **Brute force** | Login: 10/10 min per IP, 5/10 min per IP+account, 20/h per account from any IP; reset requests and booking lookups (also per booking reference across IPs) limited; refusals return 429 + `Retry-After` | `core/rate_limit.py` | rate-limit tests |
| **Shared limits** | Counters in MySQL (`rate_limit_buckets`, atomic upsert) so limits hold across workers/hosts | `DatabaseLimiter` | concurrency test (20 parallel hits, limit 7 → exactly 7 allowed) |
| **Authorisation** | Permission-based RBAC (`core/permissions.py`); every admin route declares `require(Permission…)`; refunds need `payments.refund` in addition to `bookings.manage` | `api/deps.py` | `test_permissions.py` enumerates **every** admin route from the live route table: must declare a permission, 401 when anonymous, 403 for staff where denied |
| **Mass assignment** | Admin request schemas reject unknown fields (`extra="forbid"`); updates copy only declared fields | `schemas/admin.py` | `test_unknown_fields_are_rejected_on_admin_writes` |
| **Guest data access** | Booking lookup requires reference *and* email; one error message for "no such booking" and "wrong email" | `booking_service.find_for_guest` | `test_lookup_requires_matching_email` |
| **Audit trail** | Append-only `audit_logs`: sign-ins (success/failure), password events, permission denials, CSRF rejections, rejected webhook signatures, every rate/content/settings/user change (before/after), cancellations, refunds, reconciliations, CV downloads. Written in the same transaction as the change; DB triggers reject UPDATE/DELETE; runtime account has INSERT/SELECT only | `services/audit.py`, migration | `test_audit_log_is_append_only_in_the_database`, `test_failed_change_leaves_no_audit_record` |
| **Payments** | Price computed server-side; checkout signature verified with the SDK; payment fetched from Razorpay and confirmed only if captured for the exact order/amount/currency; webhook HMAC over the raw body; dedupe by event id; explicit state machine (no backwards moves); refund requires typed confirmation of the captured amount and an intent record before calling Razorpay; external refunds on active bookings raise an alert | `services/payment_service.py`, `domain/states.py` | `test_payments.py`, `test_audit_refunds.py` |
| **Inventory** | Room-type row lock + re-check before every hold and before confirming late captures; READ COMMITTED isolation | `booking_service`, `payment_service` | `test_parallel_checkouts_do_not_oversell` |
| **Input** | Pydantic on every body/query/path; field allowlists for options; dates validated in hotel time; uploads sniffed by magic bytes, random names, CVs outside any web root; request bodies capped (1 MB JSON, 9 MB multipart) before parsing | schemas, `upload_service`, `BodySizeLimitMiddleware` | form & platform tests |
| **SQL** | SQLAlchemy expressions only; sort columns from fixed maps; no string-built SQL | repositories, routes | ruff `S` (bandit) rules pass |
| **Data minimisation** | Stored webhook payloads reduced to ids/amounts/statuses (no email, phone, VPA, card data); no card data anywhere; logs redact keys like password/secret/token/signature/card and DSN passwords | `payment_service.redact_entity`, `core/logging.py` | `test_webhook_payload_is_stored_without_customer_details` |
| **Errors** | One envelope; 5xx never include exception text, SQL or paths; every response carries `X-Request-ID` | `core/errors.py` | `test_errors_never_leak_internals` |
| **Transport / headers** | HSTS (prod), nosniff, frame DENY, Referrer-Policy, COOP; TrustedHost allowlist; CORS explicit origins with credentials (never `*` in prod); CSP in nginx | `middleware/`, `deploy/nginx.conf` | platform tests; CSP run against the production build: 0 violations |
| **Database** | Runtime account `tycoons_app`: SELECT/INSERT/UPDATE/DELETE per table, audit log INSERT/SELECT only, no DDL; Alembic uses the schema owner (`MIGRATION_DATABASE_URL`); optional TLS (`DATABASE_SSL_CA`) | `scripts/mysql-grant-app-user.ps1` | the dev API runs on this account; `SHOW GRANTS` |
| **Secrets** | Only in `.env` (git-ignored) or the host's secret store; production refuses to start with missing Razorpay keys, `COOKIE_SECURE=false`, wildcard hosts/origins, non-https `PUBLIC_BASE_URL` or in-memory rate limits | `core/config.py` | — |
| **Supply chain** | Pinned versions; `pip-audit` and `npm audit` clean at release; `detect-secrets` scan (audited exceptions marked inline) | `scripts/check.ps1`, `.github/workflows/ci.yml` | CI |

## Roles

| Permission | staff | admin |
|---|:-:|:-:|
| dashboard, bookings, payments (view) | ✓ | ✓ |
| guest requests (view, update status/notes, download CVs) | ✓ | ✓ |
| rooms/rates, content, settings (view) | ✓ | ✓ |
| cancel bookings, confirm payment-review bookings | | ✓ |
| refunds, reconcile payments | | ✓ |
| change rates, content, settings, upload images | | ✓ |
| staff users, audit log | | ✓ |

Add a role by extending `ROLE_PERMISSIONS`; nothing else changes.

## Limits and remaining risks

- **Not independently tested.** Automated tests and scanners are evidence, not proof. Commission a penetration test
  before go-live, focused on the booking/payment flow and the admin.
- **Razorpay test mode has not been run end-to-end** (no keys were provided). Signature checks use the real SDK and all
  state transitions are tested with a simulated gateway.
- **Guest booking access is reference + email.** No customer accounts or MFA exist; the lookup is rate limited per IP and
  per reference. Staff accounts have no MFA either - recommended next step (TOTP).
- **Rate limits are per IP**; behind a CDN, configure `--forwarded-allow-ips` for the CDN/proxy addresses or limits apply
  to the proxy's address.
- **Emails** (confirmations, password resets) need SMTP; until configured they are logged, which means reset links appear
  in the application log on that server.
- **`style-src 'unsafe-inline'`** remains in the CSP (React inline style attributes are used by the design's animations).
  Scripts are fully restricted.
