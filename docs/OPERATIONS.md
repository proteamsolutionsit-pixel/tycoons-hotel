# Operations runbook — The Tycoons Hotel

## Deploying a new version

1. **Back up first** (database + `backend/storage/`). Locally: `.\scripts\mysql-backup.ps1`. On a server:
   `mysqldump --single-transaction --routines --triggers tycoons > tycoons-$(date -u +%Y%m%dT%H%M%SZ).sql`
2. Install dependencies: `pip install -r requirements.txt`, `npm ci && npm run build`.
3. **Migrate** as the schema owner: run `alembic upgrade head` with `MIGRATION_DATABASE_URL` pointing at the
   schema-owner account. Review what will run with
   `alembic upgrade head --sql` first. Migrations never run on application start.
4. After migrations that add tables, refresh the runtime account's grants (`scripts/mysql-grant-app-user.ps1`, or the
   equivalent `GRANT … ON tycoons.<table>` statements: DML on application tables; `SELECT, INSERT` on `audit_logs`;
   `SELECT` on `alembic_version`).
5. `python -m app.cli seed` - idempotent; adds new settings keys only, never overwrites edited values.
6. Restart: `systemctl restart tycoons-api` (graceful: in-flight requests get 30 s).
7. Check `GET /api/v1/health/ready` → `200 {"status":"ok"}` (it returns 503 if the DB is unreachable **or the schema is
   not at the code's migration head**).

### Upgrading from 1.0 (migration `8f2012434e2d` → `e52a1c1bd47a`)

- Additive only: tables `admin_sessions`, `password_reset_tokens`, `audit_logs`, `rate_limit_buckets`; nullable <!-- pragma: allowlist secret (table name) -->
  `bookings.terms_version / terms_accepted_at / cancellation_policy`; indexes; two triggers.
- **Triggers need privilege.** With binary logging on, MySQL lets only `SUPER` (or a server with
  `log_bin_trust_function_creators=1`) create triggers. If the migration logs "audit_logs triggers NOT created", run
  `scripts/sql/audit_triggers.sql` as an administrative user. Until then the runtime grants alone keep the log append-only.
- Everyone signs in once more (JWT sessions are replaced by server-side sessions). Existing passwords keep working and are
  upgraded to Argon2id at that sign-in.
- Old URLs under `/api/...` keep working with a `Deprecation` header. **Point the Razorpay webhook at
  `https://<domain>/api/v1/payments/webhook`** at your convenience; the old URL still processes events.
- New settings: *Cancellation policy* and *Booking terms version* (Admin → Site settings). Set the real policy before
  taking bookings; it is shown at checkout and saved with each booking.

### Rolling back

| Situation | Action |
|---|---|
| Code problem, schema fine | Redeploy the previous release. 1.0 code ignores the new tables/columns. |
| Need the old schema | `alembic downgrade 8f2012434e2d` - **drops the audit log, sessions, reset tokens and terms columns**. Export `audit_logs` first if it must be kept. |
| Migration failed half-way | MySQL DDL is not transactional. Restore the pre-migration dump into an empty database, fix the cause, migrate again. (Practised on the dev copy on 2026-10-23: restore + re-run succeeded with all rows intact.) |

## Backups and restore

- Nightly: `mysqldump --single-transaction --routines --triggers` of `tycoons`, plus a copy of `backend/storage/`
  (uploaded images; CVs in `storage/private`). Keep 30 days; copy off the server; encrypt at rest (dumps contain guest
  contact details and staff password hashes).
- Restore: create an empty database, `mysql tycoons < dump.sql`, re-run the grants script, start the API, check readiness.
- Test a restore at least quarterly.

## Scheduled jobs

| Job | Schedule | Purpose |
|---|---|---|
| `python -m app.cli reconcile --older-than 10` | every 15 min | settles orders whose webhook never arrived |
| built-in housekeeper | every minute, per instance | expires lapsed holds, purges old rate-limit rows (idempotent across instances) |
| backups | nightly | see above |

## Live site (thetycoonshotel.com)

| | Staging | Live |
|---|---|---|
| URL | https://devtycoonshotel.proteam.co.in | https://thetycoonshotel.com (http and www redirect here, 301) |
| cPanel account / home | `devtycoonshotelp` · `/home3/devtycoonshotelp` | `thetycoonshotel` · `/home2/thetycoonshotel` |
| Credentials file (git-ignored) | `cpanel.txt` | `cpanel-live.txt` |
| Select with | `$env:CP_TARGET = ''` | `$env:CP_TARGET = 'live'` |
| `ENVIRONMENT` | `staging` | `production` (test payments refused; `PAYMENT_MODE=razorpay`, booking-request mode set in the admin) |
| Database | `devtycoonshotelp_tycoons` | `thetycoonshotel_tycoons` (owner `thetycoonshotel_owner`, app `thetycoonshotel_app` = DML only) |
| Mail sender | no-reply@devtycoonshotel.proteam.co.in | reservations@thetycoonshotel.com (mailbox on the same account; SPF and DKIM valid) |

Both run on the same server (78.159.97.108), Python 3.10, app root `~/tycoons`, storage `~/tycoons_storage`,
the same two cron jobs (housekeeping every 5 min, reconcile every 15 min) and the same CSP block in
`~/public_html/.htaccess`; live also has the HTTPS/www redirect block. The live `.htaccess` as it was before
the app was installed is kept as `~/public_html/.htaccess.pre-tycoons`.

Deploy to live = the staging procedure with `CP_TARGET=live`, after the same release has been checked on staging:
back up the live database, run `migrate.py` (with `Invoke-CpOnce`), upload and extract the release, restart, check.
Live holds real guest data: never copy the live database to staging or a laptop without the hotel's agreement.

## cPanel hosting (devtycoonshotel.proteam.co.in)

- CloudLinux Python Selector + Passenger, Python 3.10, app root `~/tycoons`, served through `passenger_wsgi.py` (a2wsgi).
  The ASGI lifespan never runs there, so the built-in housekeeper is replaced by a cron job:
  `cd ~/tycoons && ~/virtualenv/tycoons/3.10/bin/python -m app.cli housekeeping` every 5 min, plus the reconcile job above.
- Deploy: `scripts/build-release.ps1`, upload and extract with the helpers in `scripts/cpanel.ps1`, then
  `Restart-CpPythonApp` (touches `tmp/restart.txt`).
- **The CSP is set in `~/public_html/.htaccess`**, in the `BEGIN/END Tycoons security headers` block (from `deploy/csp.txt`),
  which also strips Passenger's `X-Powered-By`. On nginx hosts `deploy/nginx.conf` does this instead. Keep the block
  outside the CloudLinux-managed sections; re-check it after changing the app in Setup Python App.
- API docs (`/api/v1/docs`, `/openapi.json`, `/redoc`) are served only when `ENVIRONMENT` is development or test.
- Razorpay keys are entered in *Admin → Payment gateway*. Their secrets are encrypted with
  `~/tycoons_storage/private/settings.key` (or `SETTINGS_ENCRYPTION_KEY` in `.env`): include that file in backups.
  Without it a restored database has no usable secrets and the keys must be entered again.
- If every request returns Passenger's "something went wrong" page and `~/logs/tycoons.log` says
  `PassengerAgent ... No such file or directory`, the host's Passenger install is broken. Only root/WHM can fix that.

## Monitoring

- **Liveness** `GET /api/v1/health/live` (process up) - for the process supervisor.
- **Readiness** `GET /api/v1/health/ready` (DB + schema head) - for the load balancer / uptime monitor; restricted to
  localhost in `deploy/nginx.conf`.
- **Logs** are JSON lines on stdout (journald). Alert on `level=ERROR` and on these `alert` values:

| `alert` | Meaning | Action |
|---|---|---|
| `payment_review` | money captured after the hold lapsed, no room free | rehouse (raise inventory, then *Confirm booking*) or refund |
| `payment_mismatch` | Razorpay amount/order differs from ours | investigate before any manual change |
| `refund_booking_active` | refunded in Razorpay while the stay is still booked | cancel the booking or contact the guest |
| `refund_failed` | Razorpay refused a refund | retry from the dashboard or Razorpay |
| `webhook_signature` / `webhook_unknown_order` | bad or foreign webhook calls | check the webhook secret; repeated failures may be probing |
| `reconcile_failed` | Razorpay unreachable from reconciliation | transient unless persistent |

- The admin **Dashboard → Needs attention** panel shows the same signals as counts, plus failed staff sign-ins (24 h).
- Every request is logged with `request_id` (also returned as `X-Request-ID`), method, path, status, duration and the
  staff id when signed in - quote the request id from a user's error message to find the exact log line.

## Quality gates

`.\scripts\check.ps1` runs everything CI runs: ruff (incl. bandit security rules), mypy, pytest (real MySQL),
pip-audit, detect-secrets, npm audit, vitest and the production build. Exit code = number of failed gates.
