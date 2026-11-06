# Changelog — The Tycoons Hotel

Central record of every change to the application: features, fixes, security work, database, API,
configuration, dependency and deployment changes. **Newest entries first.**

## Contents

1. [Project information](#1-project-information)
2. [Maintenance rules](#2-maintenance-rules)
3. [Change history](#3-change-history)
4. [Security changes](#4-security-changes)
5. [Bug fix register](#5-bug-fix-register)
6. [Feature and enhancement register](#6-feature-and-enhancement-register)
7. [Database changes](#7-database-changes)
8. [API changes](#8-api-changes)
9. [Configuration changes](#9-configuration-changes)
10. [Dependency changes](#10-dependency-changes)
11. [Deployment and release log](#11-deployment-and-release-log)
12. [Open items and known issues](#12-open-items-and-known-issues)

---

## 1. Project information

| | |
|---|---|
| **Application** | The Tycoons Hotel — public website, room booking with online payment, and staff admin |
| **Description** | React 18 single-page site (converted from `the-tycoons-hotel.html`) and a FastAPI backend on MySQL/MariaDB with Alembic migrations; Razorpay payments (or a test payment mode); role-based staff admin with an append-only audit log |
| **Current version** | API `1.1.0` (`backend/app/main.py`); frontend package `1.0.0` (`frontend/package.json`). No release tags exist; releases are identified by commit and release-archive name (section 11) |
| **Document created** | 2026-10-26 |
| **Purpose** | Traceable history for developers, QA, security reviewers, auditors and release managers |
| **Repository** | Local git repository `G:\ProTeam\TYCOONSHOTEL` (branch `main`). GitHub remote `proteamsolutionsit-pixel/tycoons-hotel` created but **not yet pushed** (see section 12) |

### Environments

| Environment | Where | Status |
|---|---|---|
| Development | Local Windows machine: MySQL 8.4 on :3308, API :8000, Vite :5173, `ENVIRONMENT=development`, `PAYMENT_MODE=mock` | In use |
| Staging (test site) | `https://devtycoonshotel.proteam.co.in` — cPanel, CloudLinux Passenger, Python 3.10, MariaDB 10.11; `ENVIRONMENT=staging`, test payments (`PAYMENT_MODE=mock`) | In use; every "Deployed" status below refers to this environment |
| SIT / UAT | — | Not provided |
| Production | — | Not deployed. No live Razorpay keys configured |

### Related documents

- [docs/SECURITY.md](docs/SECURITY.md) — security controls and design
- [docs/AUDIT.md](docs/AUDIT.md) — audit findings and their status (backend hardening, 2026-10-23)
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — deployment, backups, scheduled jobs, monitoring, cPanel notes
- [README.md](README.md) — setup, configuration, Razorpay, roles & access

---

## 2. Maintenance rules

1. **Every modification gets an entry** — frontend, backend, database, auth, security, configuration, API,
   bug fix, feature, dependency, logging, deployment — written as part of the same task, not afterwards.
2. **Append, never rewrite history.** Correct an entry only when it is wrong, and say what was corrected.
3. **IDs:** `CHG-NNNN` (changes), `SEC-NNNN` (security), `BUG-NNNN` (bugs), `FEAT-NNNN` (features), `REL-NNNN`
   (deployments). IDs are never reused. Dates are `YYYY-MM-DD` (times, where given, are IST).
4. **Status values:** Implemented → Tested → Deployed (staging) / Deployed (production) / Rolled back.
   Pending Review where a decision is outstanding.
5. **Evidence only.** Test counts are the actual results of the run named. Anything not checked is marked
   *Not verified*; anything not known is *Not provided*. A vulnerability is called fixed only with evidence.
6. **No secrets.** Never record passwords, OTPs, API keys/secrets, tokens, private keys, or database
   credentials. Configuration entries name the key, never the value.
7. **Commit references.** Git history was rewritten on 2026-10-26 (CHG-0013); hashes quoted before that date
   in chats or notes may no longer exist. Use the hashes in this file.

---

## 3. Change history

### CHG-0019 — Occupancy-based room rates (single / double) and rate inclusions; Twin Room tariff
- **Date:** 2026-11-06 · **Version:** API 1.1.0 · **Module:** Rooms & rates, availability/pricing, booking, public site, admin
- **Change type:** Feature, Database, API · **Environment:** Development, Staging · **Status:** Deployed (staging)
- **Related commit:** `034ce29` · **Feature:** FEAT-0012 · **Release:** REL-0009

**Reason:** The hotel set the Twin Room tariff by occupancy — single occupancy ₹3,500 per night, double occupancy
₹4,500 per night, complimentary breakfast with both — and the price shown and charged must follow the occupancy.

**Previous behaviour:** One rate per room type (`base_rate_paise`), charged per room regardless of how many adults
it held. No way to state what the rate includes. The public Rooms page showed no prices.

**New behaviour:**
- Each room type has an optional **single-occupancy rate** (one adult in the room) next to the standard rate,
  which is now labelled the **double-occupancy / standard** rate, and an **inclusions** text.
- The server prices each room by its adults: a room holding one adult is charged the single rate when the
  room type has one, otherwise the standard rate. With several rooms, adults are spread as evenly as possible
  (3 adults in 2 rooms = 1 double + 1 single). **Children do not change the occupancy rate** (assumption — see Open items).
- Booking page: price for the party per night with "single occupancy" / "double occupancy" or "for 2 rooms",
  a tariff line ("Single occupancy ₹3,500 · Double occupancy ₹4,500 · Complimentary breakfast"), and a summary
  breakdown such as "(₹4,500 double + ₹3,500 single) × 1 night = ₹8,000" plus an *Includes* row.
- Rooms page: the tariff appears in the original design's `price-row__rate` slot beside *Check Availability*,
  only for room types with a single rate or inclusions configured (other rooms' prices stay unpublished).
- The booking records the single-rate rooms, the single rate and the inclusions as quoted; the guest's
  booking page, the admin booking detail and the confirmation email show them.
- Admin > Rooms & rates: fields *Single-occupancy rate per night (one adult)* (empty = standard rate) and
  *Included with the rate*; the list shows both rates.

**Files modified:**
`backend/alembic/versions/20261106_4e8b1d6f2c30_occupancy_rates.py` (new), `backend/app/models/room.py`,
`backend/app/models/booking.py`, `backend/app/services/availability.py`, `backend/app/services/booking_service.py`,
`backend/app/services/notifications.py`, `backend/app/schemas/booking.py`, `backend/app/schemas/admin.py`,
`backend/app/schemas/content.py`, `backend/app/api/routes/admin/bookings.py`, `backend/tests/test_occupancy_rates.py` (new),
`frontend/src/utils/format.js`, `frontend/src/pages/Book.jsx`, `frontend/src/pages/BookingStatus.jsx`,
`frontend/src/pages/Rooms.jsx`, `frontend/src/admin/pages/Bookings.jsx`, `frontend/src/admin/pages/RoomTypes.jsx`,
`frontend/src/styles/app.css`, `frontend/src/test/format.test.js`, `CHANGELOG.md`

**Security impact:** Prices remain computed server-side from the database; the client cannot choose the rate.
The occupancy split is derived from the validated party, not from client input.
**Database impact:** DB-0006 — five new columns, all optional or defaulted; existing prices and bookings unchanged.
**API impact:** `RoomQuote` gains `single_rate_paise`, `single_rooms`, `nightly_total_paise`, `inclusions`;
`GET /rooms` gains `single_rate_paise`, `inclusions`; booking and admin booking responses gain `single_room_count`,
`single_rate_paise`, `inclusions`; room-type admin create/update accept `single_rate_paise`, `inclusions`. Additive.
**Configuration impact:** None.

**Testing performed:**
- Backend: new `test_occupancy_rates.py` (5 tests: even split; single rate only for one-adult rooms; availability
  for 1/2 adults and with a child; booking charges and records ₹3,500; admin edit, public API, clearing the
  single rate falls back) together with `test_multi_room.py` and `test_bookings.py`: **27 passed**.
  Full backend suite (MySQL 8.4): **389 passed**.
- Frontend: **30 passed** (new tests for the tariff line and the rate breakdown).
- Browser (Edge, local): entered ₹4,500 / ₹3,500 / "Complimentary breakfast" on Twin Room in the admin form;
  Rooms page shows "Single occupancy ₹3,500 · Double occupancy ₹4,500 per night · Complimentary breakfast";
  `/book` Twin Room: 1 adult ₹3,500 (single), 2 adults ₹4,500 (double), 3 adults ₹8,000 for 2 rooms
  "(₹4,500 double + ₹3,500 single) × 1 night"; no page errors.
- Local database migrated (backup `backups/tycoons-20261106T053008Z.sql`).

**Deployment notes:** Back up → `migrate.py` (revision `4e8b1d6f2c30`) → release → restart. Done on staging
2026-11-06 (REL-0009). **Data change on staging:** Twin Room tariff set through the admin API (audited as
`room_type.update`): standard ₹6,500 → ₹4,500, single ₹3,500 (new), inclusions "Complimentary breakfast".
Staging check after deploy: 1 adult ₹3,500, 2 adults ₹4,500, 3 adults ₹8,000 for 2 rooms (1 single);
`GET /rooms` returns both rates; live bundle matches the build.
**Rollback plan:** Clear the single rate in the admin to return to one rate; or `alembic downgrade 9d4f2a7c1e85`
(drops the columns; stored booking totals remain) and redeploy the previous release.

---

### CHG-0018 — Centralised CHANGELOG.md introduced
- **Date:** 2026-10-26 · **Version:** n/a · **Module:** Documentation · **Change type:** Documentation
- **Environment:** Repository · **Status:** Implemented · **Related commit:** `ee04df0`

**Reason:** A single traceable record of all changes and security work was requested.
**Previous behaviour:** History lived only in commit messages, `docs/AUDIT.md` and chat.
**New behaviour:** This file, reconstructed from git history (17 commits), the source code, the existing docs
and the test/deployment results recorded at the time. Uncertain historical details are marked as such.
**Files modified:** `CHANGELOG.md` (new), `CLAUDE.md` (new — standing instruction to keep this file updated)
**Security / database / API / configuration impact:** None.
**Testing performed:** Not applicable (documentation). Facts cross-checked against `git log`, `git show --name-only`
and the code.
**Deployment notes:** None — not part of the release archive.

---

### CHG-0017 — Multi-room bookings for parties larger than one room
- **Date:** 2026-10-26 · **Version:** API 1.1.0 · **Module:** Booking, availability, payments, admin
- **Change type:** Feature, Database, API · **Environment:** Development, Staging
- **Status:** Deployed (staging) · **Related commit:** `031c7f2` · **Feature:** FEAT-0011 · **Release:** REL-0008

**Reason:** A party of 4 adults saw *"No rooms are available for 4 adults"* because every room sleeps 2.
The hotel wants such guests offered two rooms.

**Previous behaviour:** One booking = one room. A party exceeding one room's capacity was not bookable.

**New behaviour:** Availability works out, per room type, the fewest rooms that sleep the party — at least one
adult per room, at most 4 rooms per online booking (`max_rooms_per_booking`). Results show
"2 rooms for your party of 4 adults" and the total for all rooms; the guest pays once. If fewer rooms are free
than needed the card says so. All rooms in one booking are the same type.

**Implementation details:** `bookings.room_count`; `availability.rooms_needed()`, `fits_party(…, rooms)`,
room-weighted `peak_occupancy()`; quote = nightly rate × nights × rooms; booking creation validates the count and
holds that many rooms under the existing room-type row lock; late-payment confirmation and staff
"confirm review" require *all* rooms free; dashboard "rooms sold tonight", occupancy calendar, admin list/detail,
CSV export, confirmation email and the guest's booking page show the room count.

**Files modified:**
`backend/alembic/versions/20261026_9d4f2a7c1e85_booking_room_count.py` (new),
`backend/app/models/booking.py`, `backend/app/core/config.py`, `backend/app/repositories/bookings.py`,
`backend/app/services/availability.py`, `backend/app/services/booking_service.py`,
`backend/app/services/payment_service.py`, `backend/app/services/notifications.py`,
`backend/app/schemas/booking.py`, `backend/app/schemas/admin.py`,
`backend/app/api/routes/admin/bookings.py`, `backend/app/api/routes/admin/dashboard.py`,
`backend/tests/test_multi_room.py` (new), `backend/tests/test_bookings.py`,
`backend/tests/test_public_and_availability.py`,
`frontend/src/pages/Book.jsx`, `frontend/src/pages/BookingStatus.jsx`, `frontend/src/admin/pages/Bookings.jsx`,
`frontend/src/components/GuestPicker.jsx`, `frontend/src/styles/app.css`, `frontend/src/test/components.test.jsx`

**Security impact:** Inventory integrity preserved: the count is validated server-side and capacity re-checked
under lock; the client cannot under-count rooms (`party_too_large`) or exceed the cap (`too_many_rooms`).
**Database impact:** New column + check constraint (section 7, DB-0005). Existing bookings = 1 room.
**API impact:** `RoomQuote` gains `room_count`, `max_rooms`; `BookingCreate` accepts optional `room_count`;
booking/admin responses gain `room_count` (section 8). Backwards compatible.
**Configuration impact:** New setting `MAX_ROOMS_PER_BOOKING` (default 4).

**Testing performed:**
- Backend full suite (MySQL 8.4): **384 passed**. New `test_multi_room.py` (9 tests) and 2 updated tests
  (3 adults now bookable as 2 rooms; 1 adult + 3 children not bookable).
- Frontend: **28 passed**.
- Browser (Edge, local, test payment): 4 adults → "2 rooms for your party" → 2 × Twin Room, ₹13,000 → paid → confirmed booking page shows "2 × Twin Room".
- Defect found and fixed before commit: BUG-0009.
- Staging, after deploy (read-only availability calls): 2 adults → 1 room; 4 adults → 2 rooms bookable;
  3 adults + 2 children → 2 rooms; 1 adult + 3 children → not bookable. Admin dashboard/occupancy/bookings 200.

**Deployment notes:** Migration before code (old code ignores the new column). Done on staging with backup.
**Rollback plan:** `alembic downgrade 7b1e4c2d9a60` drops the column; multi-room bookings would then read as one
room — export them first. Redeploy the previous release archive.

---

### CHG-0016 — Booking bar: adults/children steppers; selected room listed first
- **Date:** 2026-10-26 · **Module:** Public site — booking bar, results page · **Change type:** Enhancement
- **Environment:** Development, Staging · **Status:** Deployed (staging) · **Commit:** `6e51d38`
- **Feature:** FEAT-0010 · **Release:** REL-0007

**Reason:** Guests could only choose three fixed party sizes; the room chosen in the bar was not shown first.
**Previous behaviour:** Guests `<select>` with "1 Adult", "2 Adults", "2 Adults, 1 Child". Results in server order.
**New behaviour:** A Guests button opens a panel with − / + steppers: adults 1–6, children 0–4 (the server's
limits). Shows a note when the party exceeds the largest room. URL values are clamped. On `/book` the room
selected in the bar is listed first and preselected.
**Files modified:** `frontend/src/components/GuestPicker.jsx` (new), `frontend/src/components/BookingBar.jsx`,
`frontend/src/pages/Book.jsx`, `frontend/src/styles/app.css`, `frontend/src/test/components.test.jsx`
**Security / database / API / configuration impact:** None (limits remain enforced by the API).
**Testing performed:** Frontend **28 passed** (new: stepper limits, capacity note, URL clamping). Browser: field
height matches other fields (48 px); 2 adults + 1 child with Deluxe Room → URL carries the party; Deluxe Room
listed first and preselected. Backend unchanged.
**Deployment notes:** Frontend only. **Rollback:** redeploy previous release.

---

### CHG-0015 — Staff users: sign-in email can be changed; staging administrator email changed
- **Date:** 2026-10-26 · **Module:** Admin — Staff users · **Change type:** Enhancement, Security
- **Environment:** Development, Staging · **Status:** Deployed (staging) · **Commit:** `6ec8f96`
- **Security:** SEC-0014 · **Release:** REL-0006

**Reason:** The administrator's sign-in email had to change; the admin had no way to edit an email.
**Previous behaviour:** Email fixed at creation; `PATCH /admin/users/{id}` did not accept `email`.
**New behaviour:** `email` is editable (lower-cased, unique, audited as `user.update` with from/to). A user who
manages staff cannot change the email of a user with more access (prevents account takeover via email).
**Files modified:** `backend/app/schemas/admin.py`, `backend/app/services/user_service.py`,
`backend/tests/test_roles.py`, `frontend/src/admin/pages/Users.jsx`
**Data change on staging (not code):** the single administrator account's sign-in email was changed through
this API on 2026-10-26, as requested (old address refused with 401, new address signs in, role unchanged,
recorded in the audit log). Credentials are held outside the repository.
**API impact:** `AdminUserUpdate.email` (optional). 409 `duplicate_email`; 403 `target_exceeds_own_access`.
**Testing performed:** `test_roles.py` + `test_admin.py`: **32 passed** (incl. 2 new). Frontend **26 passed**.
*The full backend suite was not re-run for this commit alone*; it passed (384) at CHG-0017, which includes it.
**Rollback:** redeploy previous release; change the email back through the admin.

---

### CHG-0014 — Roles & access: administrator-defined roles with per-permission access
- **Date:** 2026-10-26 · **Module:** Admin — authorisation, Staff users, Roles & access
- **Change type:** Feature, Security, Database, API · **Environment:** Development, Staging
- **Status:** Deployed (staging) · **Commit:** `e51b556` · **Security:** SEC-0013 · **Feature:** FEAT-0009
- **Release:** REL-0005

**Reason:** Access was fixed to two roles (admin/staff); the hotel needs per-user access control.
**Previous behaviour:** `admin_users.role` ∈ {admin, staff} mapped to fixed permission sets in code.
**New behaviour:** `roles` table. Built-in **Administrator** (always every permission; locked) and
**Front desk** (the former staff rights; editable, not deletable). Administrators create roles and tick
permissions (16 grantable, grouped Operations / Property / Administration); each user has one role. Implied
permissions are added automatically. Permissions are read on every request. Menu items follow the role; a
user whose role lacks the dashboard lands on their first permitted page.
**Implementation details:** `app/models/role.py`, `app/services/role_service.py`, `app/api/routes/admin/roles.py`;
`core/permissions.py` gains `ROLES_MANAGE`, `PERMISSION_INFO`, `IMPLIES`, `normalise()`,
`user_permissions()`/`user_can()`; `deps.require`, refund check and `/auth/me` use the user's role.
**Files modified:** `backend/alembic/versions/20261026_7b1e4c2d9a60_access_roles.py` (new),
`backend/app/models/role.py` (new), `backend/app/models/admin_user.py`, `backend/app/models/__init__.py`,
`backend/app/core/permissions.py`, `backend/app/api/deps.py`, `backend/app/api/routes/admin/__init__.py`,
`backend/app/api/routes/admin/roles.py` (new), `backend/app/api/routes/admin/auth.py`,
`backend/app/api/routes/admin/bookings.py`, `backend/app/services/role_service.py` (new),
`backend/app/services/user_service.py`, `backend/app/schemas/admin.py`, `backend/app/seed.py`, `backend/app/cli.py`,
`backend/tests/conftest.py`, `backend/tests/test_roles.py` (new), `frontend/src/admin/AdminApp.jsx`,
`frontend/src/admin/pages/Roles.jsx` (new), `frontend/src/admin/pages/Users.jsx`, `frontend/src/admin/icons.jsx`,
`frontend/src/admin/admin.css`, `frontend/src/test/admin.test.jsx`, `README.md`
**Database impact:** DB-0004. Existing users assigned automatically (admin → Administrator, staff → Front desk).
**API impact:** New `/api/v1/admin/roles` endpoints; user create/update accept `role_id`; `AdminUserOut` gains
`role_id`, `role_name`. Legacy `role` ("admin"/"staff") still accepted.
**Testing performed:** Backend full suite **373 passed** (10 new role tests incl. escalation attempts).
Frontend **26 passed**. Browser end-to-end: created role → assigned a new user → that user saw only Occupancy,
Bookings, Payments, Audit log → role deleted. Defects found and fixed before commit: BUG-0010, BUG-0011.
Staging after deploy: administrator has all 17 permissions; roles listed; admin pages 200.
**Rollback:** `alembic downgrade 3c7d9a51f0b2` (custom roles lost; users fall back to admin/staff); redeploy previous release.

---

### CHG-0013 — Repository hygiene: virtual environment removed from history; ignore rule widened
- **Date:** 2026-10-26 · **Module:** Repository · **Change type:** Configuration, Security
- **Environment:** Repository · **Status:** Implemented · **Commit:** `b28b0d1` (+ history rewrite)
- **Security:** SEC-0015

**Reason:** Preparing to push to GitHub, `backend/.venv310` (4,254 files, a Python 3.10 test virtualenv) was
found committed — `.gitignore` covered `.venv/` only.
**Previous behaviour:** History pack 19.7 MiB including the virtualenv.
**New behaviour:** The folder was removed from **every** commit (`git filter-branch --index-filter`), pack 3.5 MiB;
`.gitignore` now ignores `.venv*/`. All commit hashes from the commit that introduced it onwards changed.
**Files modified:** `.gitignore`; git history.
**Security impact:** History scanned for the project's 11 real secret values (cPanel token, database, root and
admin passwords, keys from `.env` files): **none found**.
**Testing performed:** `git ls-files backend/.venv310` → 0; `git log --all -- backend/.venv310` → 0 commits; secret scan clean.
**Rollback plan:** Original history preserved in `.tools/git-backup-20261026-104203.bundle` (verified with
`git bundle verify`).

---

### CHG-0012 — Data tables on every admin list; dashboard figures on one line
- **Date:** 2026-10-26 · **Module:** Admin — all lists, dashboard · **Change type:** Feature, Security, API
- **Environment:** Development, Staging · **Status:** Deployed (staging) · **Commit:** `16139f4`
- **Security:** SEC-0012 · **Feature:** FEAT-0008 · **Release:** REL-0004

**Reason:** Requested "datatable" behaviour on all admin tables; dashboard cards wrapped to two rows.
**New behaviour:** Bookings, Payments, Guest requests (4 kinds), Newsletter, Rooms & rates and Content tables
get search, sortable columns, rows per page (25/50/100/200), numbered pages and **Export CSV**; Staff users does
the same in the browser. Exports require the new admin-only `data.export` permission, follow the current
filters, are capped at 10,000 rows, neutralise spreadsheet formulas and are audited (`<resource>.export`).
Dashboard stat cards share one row on screens ≥ 1100 px; "1 booking" / "1 guest" pluralised.
**Files modified:** `backend/app/api/tabular.py` (new), `backend/app/api/routes/admin/bookings.py`,
`backend/app/api/routes/admin/crud.py`, `backend/app/api/routes/admin/dashboard.py`,
`backend/app/api/routes/admin/submissions.py`, `backend/app/core/permissions.py`,
`backend/tests/test_data_tables.py` (new), `frontend/src/utils/csv.js` (new), `frontend/src/admin/ui.jsx`,
`frontend/src/admin/ResourceManager.jsx`, `frontend/src/admin/admin.css`, `frontend/src/admin/pages/*`
(AuditLog, Bookings, Content, Dashboard, Payments, RoomTypes, Submissions, Users), `frontend/src/test/admin.test.jsx`
**API impact:** `q`, `sort`, `order` on list endpoints; `limit` up to 200; new `…/export` endpoints (section 8).
**Testing performed:** Backend full suite **348 passed** (15 new). Frontend **24 passed**. Browser: every table
showed search, sortable columns, page-size choice and export; each export downloaded. Dashboard: 1 row at
1920 and 1280 px, 2 rows at 1000 px, 6 at 390 px, no clipped values. Staging: sorted/searched lists and a CSV export returned 200.

---

### CHG-0011 — Audit log as a data table with CSV export
- **Date:** 2026-10-26 · **Module:** Admin — Audit log · **Change type:** Feature, API
- **Environment:** Development, Staging · **Status:** Deployed (staging) · **Commit:** `b92eaa4`
- **Feature:** FEAT-0007 · **Release:** REL-0003

**New behaviour:** Free-text search (actor, action, resource, IP, request id), sortable columns, hotel-day date
range, rows per page, numbered pages, `GET /admin/audit-logs/export` (filtered, ≤ 10,000 rows, formula-safe,
itself audited as `audit.export`). Shared pager gains page numbers; search box follows outside resets (BUG-0007).
**Files modified:** `backend/app/api/routes/admin/dashboard.py`, `backend/app/core/timeutil.py`,
`backend/tests/test_audit_table.py` (new), `frontend/src/admin/pages/AuditLog.jsx`, `frontend/src/admin/ui.jsx`,
`frontend/src/admin/admin.css`, `frontend/src/test/admin.test.jsx`
**Testing performed:** Backend targeted **62 passed** (audit, platform, admin; 6 new). Frontend **20 passed**.
Browser: sort, search, export (6 rows), clear filters. Staging: sorted list, search and date filter respond.

---

### CHG-0010 — Bookings table: uniform row height
- **Date:** 2026-10-26 · **Module:** Admin — Bookings · **Change type:** Bug Fix · **Commit:** `7da986e`
- **Status:** Deployed (staging) · **Bug:** BUG-0006 · **Release:** REL-0002

**Files modified:** `frontend/src/utils/format.js`, `frontend/src/admin/pages/Bookings.jsx`,
`frontend/src/admin/admin.css`, `frontend/src/test/format.test.js`
**Testing performed:** Frontend **18 passed** (new `stayRange` test). Browser at 1280 px × 1.25: all rows 67 px,
no horizontal overflow. Staging bundle hash matched the local build.

---

### CHG-0009 — `migrate.py`: run migrations without a shell
- **Date:** 2026-10-24 · **Module:** Operations · **Change type:** Deployment · **Commit:** `6a6e705`
- **Status:** Deployed (staging) — used for every migration since

**Reason:** The cPanel host has no SSH; migrations had to be runnable from cPanel's "Execute python script" or cron.
**Files modified:** `backend/migrate.py` (new), `scripts/build-release.ps1` (includes it in the release)
**Testing performed:** Local test database downgraded one revision, `migrate.py` upgraded it ("OK - migration
applied"); second run reported "Already up to date". Used on staging for DB-0003, DB-0004, DB-0005.

---

### CHG-0008 — Admin > Payment gateway: payment mode and Razorpay keys from the admin
- **Date:** 2026-10-24 · **Module:** Payments, Admin · **Change type:** Feature, Security, Database, API
- **Environment:** Development, Staging · **Status:** Deployed (staging) — deployment delayed to 2026-10-26 (see REL-0001)
- **Commit:** `ca40157` · **Security:** SEC-0011 · **Feature:** FEAT-0006

**Reason:** Razorpay keys could only be set by editing the server `.env`.
**New behaviour:** Admin-only page (`payments.settings`) to choose test payments or Razorpay, enter Key Id, Key
Secret and webhook secret, test the keys with one read-only Razorpay call, or revert to the server
configuration. Saved values take precedence over the environment and apply on the next request. Switching to
`rzp_live_` keys requires typing `LIVE`. Test payments cannot be selected in production.
**Files modified:** `backend/alembic/versions/20261024_3c7d9a51f0b2_payment_gateway_settings.py` (new),
`backend/app/core/secretbox.py` (new), `backend/app/models/payment_settings.py` (new),
`backend/app/services/payment_settings_service.py` (new), `backend/app/api/routes/admin/payment_settings.py` (new),
`backend/app/services/razorpay_gateway.py`, `backend/app/core/config.py`, `backend/app/core/permissions.py`,
`backend/app/schemas/admin.py`, `backend/app/models/__init__.py`, `backend/app/api/routes/admin/__init__.py`,
`backend/app/cli.py`, `backend/tests/conftest.py`, `backend/tests/test_payment_settings.py` (new),
`backend/.env.example`, `frontend/src/admin/pages/PaymentSettings.jsx` (new), `frontend/src/admin/AdminApp.jsx`,
`frontend/src/admin/icons.jsx`, `frontend/src/test/admin.test.jsx`, `scripts/mysql-grant-app-user.ps1` (BUG-0005),
`README.md`, `docs/OPERATIONS.md`
**Configuration impact:** `SETTINGS_ENCRYPTION_KEY` (optional); otherwise a key file is generated at
`STORAGE_DIR/private/settings.key` on first save — it must be included in backups.
**Testing performed:** Backend full suite **297 passed** (16 new). Frontend **17 passed**. Browser: connection
test reached Razorpay (fake keys correctly rejected), live-key confirmation shown, save and reset worked; no
horizontal overflow at 390 px. Staging after deploy: page loads, reports test payments from server configuration.
**Rollback:** `alembic downgrade e52a1c1bd47a` drops saved settings (environment applies again).

---

### CHG-0007 — API docs hidden outside development; CSP and header changes on the staging host
- **Date:** 2026-10-23 · **Module:** Platform, hosting · **Change type:** Security, Configuration
- **Environment:** Staging · **Status:** Deployed (staging) · **Commit:** `ed2420f` · **Security:** SEC-0009, SEC-0007

**Reason:** First live check of staging found the CSP header missing (it was configured for nginx, which this
Apache host does not use), Passenger advertising its version, and Swagger/ReDoc/OpenAPI publicly served.
**New behaviour:** `/api/v1/docs`, `/redoc`, `/openapi.json` served only when `ENVIRONMENT` is development or test.
On the staging host, `public_html/.htaccess` gained a `BEGIN/END Tycoons security headers` block setting the CSP
from `deploy/csp.txt` and removing `X-Powered-By` (server file, not in the repository; previous file backed up
to `.tools/server-backup/`).
**Files modified:** `backend/app/main.py`, `README.md`, `docs/OPERATIONS.md`; server: `public_html/.htaccess`
**Testing performed:** `tests/test_platform.py` **24 passed**. Staging: CSP present, `X-Powered-By` absent, docs URLs 404, readiness 200.

---

### CHG-0006 — Python 3.10 compatibility; cPanel deploy helper fixes
- **Date:** 2026-10-23 · **Module:** Backend platform, scripts · **Change type:** Bug Fix, Dependency, Deployment
- **Status:** Deployed (staging) · **Commit:** `5c04f13` · **Bugs:** BUG-0003, BUG-0004

**Reason:** The cPanel host offers Python 3.10 only.
**Files modified:** `backend/app/core/logging.py`, `backend/app/core/timeutil.py`, `backend/pyproject.toml`,
`backend/requirements.txt`, `backend/requirements-server.txt`, `scripts/cpanel.ps1`
**Testing performed:** Full suite on Python 3.10.11: **269 passed**.

---

### CHG-0005 — Hosting preparation for cPanel; MariaDB compatibility
- **Date:** 2026-10-23 · **Module:** Backend platform, operations · **Change type:** Deployment, Bug Fix
- **Status:** Deployed (staging) · **Commit:** `ba358fc` · **Bugs:** BUG-0001, BUG-0002

**New behaviour:** `staging` environment (production safeguards, test payments allowed); `passenger_wsgi.py`
(a2wsgi); `requirements-server.txt`; `app.cli housekeeping` for cron (Passenger runs no lifespan);
`scripts/cpanel.ps1` and `scripts/build-release.ps1`.
**Files modified:** `.gitignore`, `backend/alembic/versions/20261023_e52a1c1bd47a_…py`, `backend/app/cli.py`,
`backend/app/core/config.py`, `backend/app/main.py`, `backend/app/middleware/request_context.py`,
`backend/app/repositories/bookings.py`, `backend/passenger_wsgi.py` (new), `backend/requirements-server.txt` (new),
`backend/requirements.txt`, `backend/tests/test_audit_refunds.py`, `backend/tests/test_platform.py`,
`scripts/build-release.ps1` (new), `scripts/cpanel.ps1` (new)
**Testing performed:** MySQL 8.4 **269 passed**; MariaDB 10.11.19 **268 passed, 1 skipped** (trigger test needs SUPER).

---

### CHG-0004 — Test payment mode (`PAYMENT_MODE=mock`)
- **Date:** 2026-10-23 · **Module:** Payments, public site · **Change type:** Feature, Configuration
- **Status:** Deployed (staging; active there) · **Commit:** `3fdaf7c` · **Feature:** FEAT-0005 · **Security:** SEC-0010

**Reason:** Bookings needed testing before a Razorpay account (PAN verification) was available.
**New behaviour:** A mock gateway replaces only Razorpay's network calls; orders, holds, HMAC signature
verification, state machine, refunds, reconcile and audit run the real code. `POST /api/v1/payments/mock/checkout`
(404 unless mock mode). The site shows a labelled test payment window.
**Files modified:** `backend/app/services/mock_gateway.py` (new), `backend/app/services/razorpay_gateway.py`,
`backend/app/services/payment_service.py`, `backend/app/services/booking_service.py`,
`backend/app/api/routes/payments.py`, `backend/app/core/config.py`, `backend/app/main.py`,
`backend/app/schemas/booking.py`, `backend/tests/test_mock_payments.py` (new), `backend/.env.example`,
`frontend/src/services/mockCheckout.jsx` (new), `frontend/src/services/razorpay.js`, `frontend/src/styles/app.css`, `README.md`
**Testing performed:** 8 new tests (per commit message); browser booking in Edge: failure, retry, confirmation, admin view.

---

### CHG-0003 — Admin redesign, CSP, operations and security documentation
- **Date:** 2026-10-23 · **Module:** Admin UI, deployment config, docs · **Change type:** Enhancement, Security, Documentation
- **Status:** Deployed (staging) · **Commit:** `92f663c` · **Security:** SEC-0007

**New behaviour (per commit message):** Permission-aware admin shell, sortable tables, occupancy calendar,
dashboard KPIs/alerts, booking detail with terms, typed-confirmation refund dialog, payment-review resolution,
audit-log viewer, forgot/reset password; frontend moved to `/api/v1`; inline script removed for a strict CSP;
nginx CSP/HSTS/host allowlist and hardened systemd unit; `docs/AUDIT.md`, `docs/SECURITY.md`, `docs/OPERATIONS.md`.
**Files modified:** 32 files — `deploy/*`, `docs/*`, `frontend/index.html`, `frontend/public/motion-flag.js`,
`frontend/src/admin/**`, `frontend/src/pages/Book.jsx`, `frontend/src/pages/BookingStatus.jsx`,
`frontend/src/services/api.js`, `frontend/src/main.jsx`, tests, `README.md`
**Testing performed (per commit message):** 261 backend + 15 frontend tests; ruff, mypy, pip-audit, npm audit,
detect-secrets clean; CSP verified on the production build with 0 violations. *Not re-verified for this document.*

---

### CHG-0002 — Backend security hardening and refactor
- **Date:** 2026-10-23 · **Module:** Backend (all) · **Change type:** Security, Database, Dependency, API
- **Status:** Deployed (staging) · **Commit:** `6a2add6` · **Security:** SEC-0001 … SEC-0008

**Reason:** Requested professional refactor and OWASP-oriented hardening (findings in [docs/AUDIT.md](docs/AUDIT.md)).
**New behaviour (per commit message):** patched dependencies; server-side staff sessions with idle/absolute expiry
and session-bound CSRF; Argon2id with bcrypt upgrade; password policy and email password reset; permission
check on every admin route; append-only audit log (DB triggers); shared MySQL rate limiter; booking/payment
state machine; refund eligibility and amount confirmation; booking terms snapshot; redacted webhook payloads;
`/api/v1` with deprecated `/api` alias; body-size limit, trusted hosts, HSTS, log redaction, health live/ready;
restricted runtime DB account; migration `e52a1c1bd47a`; services extracted from routes; CI workflow.
**Files modified:** 70+ files under `backend/`, `.github/workflows/ci.yml`, `.gitignore`, `README.md`
(see `git show --stat 6a2add6`).
**Testing performed (per commit message):** 185 backend tests. *Not re-verified for this document.*

---

### CHG-0001 — Initial full-stack conversion
- **Date:** 2026-10-23 · **Module:** All · **Change type:** Feature · **Status:** Deployed (staging) · **Commit:** `8eabf24`
- **Feature:** FEAT-0001 … FEAT-0004

Conversion of `the-tycoons-hotel.html` into a React frontend (8 pages, original CSS kept verbatim) and a FastAPI
backend with Alembic schema `8f2012434e2d`: room booking with Razorpay payments and webhooks, guest request
forms, staff admin, tests. Test results for this commit: *Not provided* in the commit message.

---

## 4. Security changes

Detailed controls: [docs/SECURITY.md](docs/SECURITY.md); findings: [docs/AUDIT.md](docs/AUDIT.md).
"Verified" = automated tests and/or a recorded live check at the time.

| ID | Date | Area | Concern | Remediation | Evidence | Residual risk / limits | Ref | Status |
|---|---|---|---|---|---|---|---|---|
| SEC-0016 | 2026-10-23 | Database hosting | Remote MySQL access to the staging DB from an external IP | Remote-access host removed in cPanel; DB users scoped to `localhost`; app account limited to DML | External login refused (checked 2026-10-23) | — | OWASP A05 | Verified (staging) |
| SEC-0015 | 2026-10-26 | Repository | Third-party code (virtualenv) in history; risk of secrets in history before publishing | Virtualenv removed from all commits; `.venv*/` ignored; full-history scan for 11 real secret values | Scan: none found | Remote not yet pushed; scan covers known secrets only | CWE-540 | Verified |
| SEC-0014 | 2026-10-26 | Staff accounts | Email change could be used to take over a higher-privileged account | Email editable only within the editor's own access; unique; audited | Tests: change, duplicate 409, HR user → admin email 403 | — | CWE-639, OWASP A01 | Verified; deployed |
| SEC-0013 | 2026-10-26 | Authorisation (RBAC) | Fixed two-role model; need least privilege without escalation paths | Custom roles; `roles.manage` never grantable; assign only roles ⊆ own permissions; cannot modify users with more access (incl. password reset); last admin protected; role in use not deletable; per-request permission evaluation; audited diffs | 10 role tests incl. self-promotion, admin password reset, deactivation attempts → 403 | Front desk role editable by admins; permission granularity is per screen/action, not per record | CWE-269, CWE-285, OWASP A01 | Verified; deployed |
| SEC-0012 | 2026-10-26 | Data export | Bulk export of guest PII; CSV/formula injection; LIKE wildcard abuse | `data.export` admin-only permission; ≤ 10,000 rows; values beginning `= + - @ \t \r` prefixed with `'`; every export audited with row count and filters; LIKE wildcards in searches escaped | Tests: staff 403 on 6 export endpoints; `'=` prefix asserted; audit row asserted | Exported files leave the system's control once downloaded | CWE-1236, OWASP A01 | Verified; deployed |
| SEC-0011 | 2026-10-24 | Payment secrets | Razorpay secrets editable from the admin must not be readable from the DB or API | Fernet encryption, key outside the DB (`SETTINGS_ENCRYPTION_KEY` or key file); secrets never returned; audit records only *whether* a secret changed; fail closed if the key is lost; live keys need typed confirmation | Tests: ciphertext ≠ plaintext, API/audit contain no secret, lost key → payments off | Key file must be backed up and protected; host compromise exposes both | CWE-312, OWASP A02 | Verified; deployed |
| SEC-0010 | 2026-10-23 | Payments | Test payments must never run in production | Config validation refuses `PAYMENT_MODE=mock` in production; gateway ignores a saved mock mode in production; mock endpoint 404 unless mock mode | `test_production_refuses_mock_mode`, `test_test_payments_cannot_be_chosen_in_production` | Staging deliberately allows test payments | — | Verified |
| SEC-0009 | 2026-10-23 | API surface | Full API map (Swagger/OpenAPI) public on staging | Docs only in development/test | Staging: docs URLs 404 | — | OWASP A05 | Verified; deployed |
| SEC-0008 | 2026-10-23 | Database | Application ran with schema-owner rights | Restricted runtime account (DML only; `audit_logs` SELECT/INSERT locally); migrations use the owner account | Per commit `6a2add6` | On staging the app account has database-level DML (cPanel), not per-table | OWASP A05 | Verified (per commit) |
| SEC-0007 | 2026-10-23 | Transport / headers | Missing CSP on Apache host; server version disclosure | CSP (nginx config, and `.htaccess` on staging), HSTS, nosniff, frame-deny, referrer & permissions policy; `X-Powered-By` removed | Staging header check 2026-10-23 | CSP allows `'unsafe-inline'` styles | OWASP A05 | Verified (staging) |
| SEC-0006 | 2026-10-23 | Payments integrity | Amount tampering, forged confirmations, duplicate bookings | Server-side pricing; HMAC signature verification; payment state machine; idempotency keys; webhook payload redaction | Live: forged signature → 400; idempotent replay → same booking | — | CWE-345 | Verified |
| SEC-0005 | 2026-10-23 | Dependencies | Outdated packages with known advisories | Upgrades listed in section 10 | pip-audit / npm audit clean (per commit `6a2add6`, `92f663c`) | Re-audit before production | OWASP A06 | Verified (per commit) |
| SEC-0004 | 2026-10-23 | Brute force / abuse | Login and form abuse | Shared MySQL-backed rate limiter (per IP and per account) | Per commit `6a2add6` | — | CWE-307 | Verified (per commit) |
| SEC-0003 | 2026-10-23 | Authorisation & audit | Admin routes without per-action checks; mutable audit trail | Permission dependency on every admin route (enumerated by `test_permissions.py`); append-only audit log with DB triggers | Tests; MariaDB without SUPER: triggers skipped, append-only relies on grants | Triggers absent on staging (no SUPER) | OWASP A01, A09 | Verified |
| SEC-0002 | 2026-10-23 | Passwords | Weak hashing / policy | Argon2id (bcrypt hashes upgraded on login); 12+ chars with mixed case, digits, no common words; email reset tokens hashed | Tests; policy observed rejecting a weak test password 2026-10-26 | Email delivery (SMTP) not configured — reset emails are logged only | OWASP A07 | Verified |
| SEC-0001 | 2026-10-23 | Sessions | Stateless tokens; CSRF | Server-side sessions (opaque token, SHA-256 stored), idle 30 min / absolute 12 h, revocation; CSRF token bound to session; cookies HttpOnly + Secure + SameSite | Staging: cookies flagged; request without CSRF header → 403 and audited | — | OWASP A07, CWE-352 | Verified |

---

## 5. Bug fix register

| ID | Description | Reproduce | Root cause | Fix | Files | Regression tests | Status |
|---|---|---|---|---|---|---|---|
| BUG-0011 | Audit details of a role update lost the permission lists | Update a role's permissions; read `role.update` details | Audit sanitiser trims nesting deeper than 3 levels | Flattened to `permissions_added` / `permissions_removed` | `role_service.py` | `test_role_changes_apply_on_the_next_request` | Fixed before release (CHG-0014) |
| BUG-0010 | Blank admin page for a role without the dashboard | Sign in as such a role; open a page it may not see | Guard redirected to `/admin`, which the role also cannot see | Redirect to the first permitted menu page; message if none | `AdminApp.jsx` | Browser check (redirect to Occupancy) | Fixed before release (CHG-0014) |
| BUG-0009 | Occupancy calendar crash after multi-room change | Open occupancy with bookings | Room-count variable reused the loop's date variable name | Renamed | `dashboard.py` | `test_paid_two_room_booking_counts_two_in_admin` | Fixed before release (CHG-0017) |
| BUG-0008 | Party > room size reported "No rooms available" | Search 4 adults | One-room-per-booking model | Multi-room bookings | see CHG-0017 | `test_multi_room.py` | Fixed; deployed |
| BUG-0007 | "Clear filters" left the search text and re-applied it | Search, then Clear filters | Search box did not follow outside value changes | Box syncs to its value prop | `ui.jsx` | Browser check | Fixed; deployed (CHG-0011) |
| BUG-0006 | Bookings rows of uneven height | Narrow screen / zoom | Long weekday dates wrapped in a narrow column | Compact range, no-wrap cells, two-line created time | see CHG-0010 | `stayRange` test; browser | Fixed; deployed |
| BUG-0005 | Grant script failed re-running ("CREATE USER failed") | Run `mysql-grant-app-user.ps1` twice | Existing-user check expected 1 row; there are 2 (two hosts) | Check `> 0` | `scripts/mysql-grant-app-user.ps1` | Re-run succeeded (21 tables) | Fixed |
| BUG-0004 | cPanel uploads ignored target folder / failed | Upload via `Send-CpFile` | Unquoted multipart field names | Quoted names, explicit Content-Disposition | `scripts/cpanel.ps1` | Uploads to correct folder | Fixed |
| BUG-0003 | Startup failure on Python 3.10 | Run on 3.10 | `datetime.UTC` (3.11+) | `timezone.utc`; version markers | see CHG-0006 | Suite on 3.10.11: 269 passed | Fixed; deployed |
| BUG-0002 | Migration failed on hosts without SUPER (error 1419) | Upgrade on MariaDB with binlog | Trigger DDL needs SUPER | Trigger creation/drop tolerates 1419/1227/1142 | migration `e52a1c1bd47a` | MariaDB suite: 268 passed, 1 skipped | Fixed |
| BUG-0001 | Deadlock on MariaDB when locking bookings | Concurrent booking operations | MariaDB lacks `FOR UPDATE OF`; the joined row was locked too | Lock without joining `room_types` | `repositories/bookings.py` | Concurrency tests on MariaDB | Fixed; deployed |

---

## 6. Feature and enhancement register

| ID | Feature | Requirement | Behaviour | Change | Config needed | Tests | Release status |
|---|---|---|---|---|---|---|---|
| FEAT-0012 | Occupancy-based rates + inclusions | Twin Room: single ₹3,500, double ₹4,500, breakfast included | Single rate for one-adult rooms; tariff and breakdown shown | CHG-0019 | Enter rates per room type in the admin | 389 backend, 30 frontend | Deployed (staging) |
| FEAT-0011 | Multi-room bookings | Offer enough rooms when a party exceeds one room | Fewest rooms per type; one payment | CHG-0017 | `MAX_ROOMS_PER_BOOKING` (optional) | 384 backend, 28 frontend | Deployed (staging) |
| FEAT-0010 | Guest steppers; chosen room first | Any party size; respect selection | − / + adults & children; chosen room first | CHG-0016 | — | 28 frontend | Deployed (staging) |
| FEAT-0009 | Roles & access | Per-user access | Custom roles, permission checklist | CHG-0014 | — | 373 backend, 26 frontend | Deployed (staging) |
| FEAT-0008 | Admin data tables + CSV export | "Datatable" on all tables | Search/sort/page size/pages/export | CHG-0012 | — | 348 backend, 24 frontend | Deployed (staging) |
| FEAT-0007 | Audit log data table | As above, audit log first | Search, sort, dates, export | CHG-0011 | — | 62 targeted, 20 frontend | Deployed (staging) |
| FEAT-0006 | Payment gateway settings | Manage Razorpay from the admin | Mode, keys, test, reset | CHG-0008 | `SETTINGS_ENCRYPTION_KEY` (optional) | 297 backend, 17 frontend | Deployed (staging) |
| FEAT-0005 | Test payment mode | Book without a Razorpay account | Mock gateway + test window | CHG-0004 | `PAYMENT_MODE=mock` | 8 new tests | Deployed (staging, active) |
| FEAT-0004 | Staff admin | Manage bookings, content, users | Admin SPA | CHG-0001/0003 | — | per commits | Deployed (staging) |
| FEAT-0003 | Guest request forms | Dining, spa, enquiries, careers, newsletter | Stored and listed in admin | CHG-0001 | — | per commit | Deployed (staging) |
| FEAT-0002 | Room booking with online payment | Full prepayment | Availability, hold, Razorpay | CHG-0001 | Razorpay keys (not yet provided) | per commit | Deployed (staging, test mode) |
| FEAT-0001 | Website conversion | Preserve the HTML design | React pages, original CSS | CHG-0001 | — | Visual regression pixel-identical (per project notes) | Deployed (staging) |

---

## 7. Database changes

Migrations live in `backend/alembic/versions/`. Apply with `python migrate.py` (or `alembic upgrade head`)
using the schema-owner account; **back up first**. Order on deploy: migration, then code.

| ID | Revision | Date | Change | Data transformation | Rollback | Staging |
|---|---|---|---|---|---|---|
| DB-0006 | `4e8b1d6f2c30` | 2026-11-06 | `room_types.single_rate_paise` (NULL), `room_types.inclusions` ('') + check single rate ≥ 0; `bookings.single_room_count` (0), `bookings.single_rate_paise` (NULL), `bookings.inclusions` (NULL) | None | `alembic downgrade 9d4f2a7c1e85` | Applied 2026-11-06 after backup `tycoons-20261106T054549Z.sql.gz` |
| DB-0005 | `9d4f2a7c1e85` | 2026-10-26 | `bookings.room_count INT NOT NULL DEFAULT 1` + check `room_count >= 1` | None (existing = 1) | `alembic downgrade 7b1e4c2d9a60` (multi-room bookings read as 1 room) | Applied 2026-10-26 after backup `tycoons-20261026T070541Z.sql.gz` |
| DB-0004 | `7b1e4c2d9a60` | 2026-10-26 | `roles` table; `admin_users.role_id` (FK RESTRICT, indexed) | Inserts Administrator & Front desk; sets every user's `role_id` from `role` | `alembic downgrade 3c7d9a51f0b2` (custom roles lost) | Applied 2026-10-26 after backup `tycoons-20261026T054816Z.sql.gz` |
| DB-0003 | `3c7d9a51f0b2` | 2026-10-24 | `payment_gateway_settings` (single row; encrypted secret columns) | None | `alembic downgrade e52a1c1bd47a` (saved keys lost) | Applied 2026-10-26 after backup `tycoons-20261026T035748Z.sql.gz` |
| DB-0002 | `e52a1c1bd47a` | 2026-10-23 | Sessions, password-reset tokens, audit log, rate-limit tables; 3 nullable booking columns; indexes; append-only triggers | None | `alembic downgrade 8f2012434e2d` (drops audit trail/sessions) | Applied at first deploy; triggers not created (no SUPER) |
| DB-0001 | `8f2012434e2d` | 2026-10-23 | Initial schema | Seed data via `app.cli seed` | — | Applied at first deploy |

Backups are written to `~/backups/` on the staging host (mode 0700, files 0600) and `backups/` locally (git-ignored).

---

## 8. API changes

Base path `/api/v1` (legacy `/api/...` still answers with `Deprecation: true`).

| Date | Change | Endpoint(s) | Auth | Compatibility |
|---|---|---|---|---|
| 2026-11-06 | Occupancy rates | `GET /bookings/availability` quotes gain `single_rate_paise`, `single_rooms`, `nightly_total_paise`, `inclusions`; `GET /rooms` gains `single_rate_paise`, `inclusions`; booking responses gain `single_room_count`, `single_rate_paise`, `inclusions`; `POST/PATCH /admin/room-types` accept `single_rate_paise`, `inclusions` | Public / `catalog.manage` | Additive |
| 2026-10-26 | Multi-room quotes and bookings | `GET /bookings/availability` → `room_count`, `max_rooms`; `POST /bookings` accepts `room_count`; booking & admin responses gain `room_count` | Public / admin | Additive |
| 2026-10-26 | Email editable | `PATCH /admin/users/{id}` accepts `email` (409 `duplicate_email`, 403 `target_exceeds_own_access`) | `users.manage` | Additive |
| 2026-10-26 | Roles | `GET/POST /admin/roles`, `PATCH/DELETE /admin/roles/{id}`, `GET /admin/roles/permissions`; users accept `role_id`; `AdminUserOut.role_id`, `role_name`; new 403 codes `role_exceeds_own_access`, `target_exceeds_own_access`; 409 `last_admin`, `system_role`, `in_use` | `users.manage` (read), `roles.manage` (write) | Additive; legacy `role` still accepted |
| 2026-10-26 | Data tables | `q`, `sort`, `order` on bookings, payments, submissions, newsletter, all content lists; `limit` ≤ 200; `GET …/export` on bookings, payments, `submissions/{kind}`, newsletter, each content list | View permission + `data.export` for exports | Additive |
| 2026-10-26 | Audit log table | `GET /admin/audit-logs` gains `q`, `sort`, `order`, `date_from`, `date_to`; `GET /admin/audit-logs/export` | `audit.view` | Additive |
| 2026-10-24 | Payment gateway | `GET/PUT/DELETE /admin/payment-settings`, `POST /admin/payment-settings/test` | `payments.settings` | New |
| 2026-10-23 | Docs hidden | `/api/v1/docs`, `/redoc`, `/openapi.json` → 404 outside development/test | — | Breaking only for tooling that read the live OpenAPI |
| 2026-10-23 | Test payments | `POST /payments/mock/checkout` (404 unless mock mode); `CheckoutConfig.mode` | Public | Additive |
| 2026-10-23 | Versioned API | `/api/v1/*`; `/api/*` deprecated alias | — | Backwards compatible |

---

## 9. Configuration changes

Values are never recorded here. Restart = touch `tmp/restart.txt` on cPanel (`Restart-CpPythonApp`).

| Key / item | Purpose | Environments | Restart? | Change |
|---|---|---|---|---|
| `MAX_ROOMS_PER_BOOKING` | Cap rooms per online booking (default 4) | All | Yes | CHG-0017 |
| `SETTINGS_ENCRYPTION_KEY` / `STORAGE_DIR/private/settings.key` | Encrypt admin-entered payment secrets | All | Yes (env) | CHG-0008 |
| `ENVIRONMENT=staging` | Production safeguards with test payments | Staging | Yes | CHG-0005 |
| `PAYMENT_MODE` (`razorpay` / `mock`) | Payment gateway; overridden by Admin > Payment gateway once saved | All (mock refused in production) | Yes | CHG-0004 / CHG-0008 |
| `COOKIE_SECURE`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`, `RATE_LIMIT_BACKEND=database` | Enforced for staging/production by config validation | Staging, Production | Yes | CHG-0002 |
| `DATABASE_URL` (runtime account), `MIGRATION_DATABASE_URL` (owner) | Least-privilege DB access | All | Yes | CHG-0002 |
| `FRONTEND_DIST`, `STORAGE_DIR` | Serve the built site; uploads/private files outside the web root | Staging | Yes | CHG-0005 |
| Cron: `app.cli housekeeping` every 5 min; `app.cli reconcile --older-than 10` every 15 min | Expire holds, purge rate-limit rows; settle unconfirmed payments | Staging | No | 2026-10-23 |
| `public_html/.htaccess` security-headers block | CSP, remove `X-Powered-By` | Staging | No | CHG-0007 |
| `.gitignore`: `.venv*/` | Keep virtualenvs out of git | Repository | No | CHG-0013 |

---

## 10. Dependency changes

| Date | Package | Old → New | Reason | Change |
|---|---|---|---|---|
| 2026-10-23 | fastapi | 0.115.12 → 0.161.1 | Security / currency | CHG-0002 |
| 2026-10-23 | starlette | (transitive) → 1.9.0 (Python ≥ 3.11) / 1.7.0 (Python 3.10) | Security; 3.10 host | CHG-0002, CHG-0006 |
| 2026-10-23 | uvicorn[standard] | 0.34.2 → 0.54.0 | Currency | CHG-0002 |
| 2026-10-23 | SQLAlchemy | 2.0.40 → 2.0.55 | Currency | CHG-0002 |
| 2026-10-23 | PyMySQL | 1.1.1 → 1.2.3 | Currency | CHG-0002 |
| 2026-10-23 | cryptography | 44.0.3 → 50.0.2 | Security | CHG-0002 |
| 2026-10-23 | alembic | 1.15.2 → 1.20.1 | Currency | CHG-0002 |
| 2026-10-23 | pydantic / pydantic-settings | 2.11.4 → 2.14.1 / 2.9.1 → 2.16.1 (2.15.0 on 3.10) | Currency | CHG-0002, CHG-0006 |
| 2026-10-23 | email-validator, python-multipart | 2.2.0 → 2.3.0, 0.0.20 → 0.0.32 | Security / currency | CHG-0002 |
| 2026-10-23 | razorpay | 1.4.2 → 2.0.1 | Currency | CHG-0002 |
| 2026-10-23 | bcrypt; argon2-cffi | 4.3.0 → 5.0.0; added 25.1.0 | Argon2id hashing | CHG-0002 |
| 2026-10-23 | PyJWT | 2.10.1 → removed | Replaced by server-side sessions | CHG-0002 |
| 2026-10-23 | setuptools, tzdata | 80.9.0 → 84.2.1, 2025.2 → 2026.5 | Currency | CHG-0002 |
| 2026-10-23 | a2wsgi | added 1.10.10 | WSGI bridge for Passenger | CHG-0005 |
| 2026-10-23 | react-router-dom, gsap | 6.28.0 → 7.18.4, 3.12.5 → 3.15.0 | Security / currency | CHG-0002 |
| 2026-10-23 | vite, vitest, jsdom, @vitejs/plugin-react, Testing Library | 5.4.11 → 6.4.5, 2.1.8 → 5.0.5, 25.0.1 → 26.1.0, 4.3.4 → 4.7.0, jest-dom 6.6.3 → 6.9.1, react 16.1.0 → 16.3.3, user-event 14.5.2 → 14.6.8 | Security / currency (dev) | CHG-0002 |

Audit results at the time: pip-audit and npm audit clean (per commits `6a2add6`, `92f663c`). *Not re-run for this document.*

---

## 11. Deployment and release log

Staging deploys use `scripts/build-release.ps1` → `Send-CpFile` → `Expand-CpArchive` into `~/tycoons` →
restart. Migrations run first, from cron with `migrate.py`, after a `mysqldump` to `~/backups/`. Temporary
credentials files and one-off cron jobs are removed after each deploy.

| ID | Date | Release archive | Contents | Migration | Verification |
|---|---|---|---|---|---|
| REL-0009 | 2026-11-06 | `tycoons-20261106T054735Z` | CHG-0019 (+ Twin Room tariff entered) | `4e8b1d6f2c30` | Twin: 1 adult ₹3,500, 2 adults ₹4,500, 3 adults ₹8,000/2 rooms; bundle matched |
| REL-0008 | 2026-10-26 | `tycoons-20261026T070733Z` | CHG-0017 | `9d4f2a7c1e85` | Availability for 2/4/3+2/1+3 guests as expected; admin pages 200 |
| REL-0007 | 2026-10-26 | `tycoons-20261026T061633Z` | CHG-0016 | — | Live bundle = local build; ready 200 |
| REL-0006 | 2026-10-26 | `tycoons-20261026T055445Z` | CHG-0015 (+ admin email changed via API) | — | New email signs in; old refused |
| REL-0005 | 2026-10-26 | `tycoons-20261026T055004Z` | CHG-0014 | `7b1e4c2d9a60` | Administrator role with 17 permissions; roles listed |
| REL-0004 | 2026-10-26 | `tycoons-20261026T044455Z` | CHG-0012 | — | Sorted/searched lists, CSV export 200 |
| REL-0003 | 2026-10-26 | `tycoons-20261026T042502Z` | CHG-0011 | — | Audit sort/search/date filter 200 |
| REL-0002 | 2026-10-26 | `tycoons-20261026T041421Z` | CHG-0010 | — | Bundle hash matched |
| REL-0001 | 2026-10-26 | `tycoons-20261024T061826Z` | CHG-0008, CHG-0009 | `3c7d9a51f0b2` | Payment gateway page live; admin bundle contains it |
| REL-0000 | 2026-10-23 | first release + `main.py` hot fix | CHG-0001 … CHG-0007 | `8f2012434e2d`, `e52a1c1bd47a` | Site, booking (test mode), payment verify, forged-signature 400, admin, cookies, CSRF |

**Incidents**
- 2026-10-23 — staging returned 500 on every request: the host's Passenger install was missing `PassengerAgent`. Resolved by the hosting provider; no application change.
- 2026-10-24 → 2026-10-26 — the server firewall dropped the office IP on all ports after heavy cPanel API use, delaying REL-0001. Deployment resumed from a different IP; the original IP may still need whitelisting.

---

## 12. Open items and known issues

| Item | Detail | Owner |
|---|---|---|
| Child pricing (CHG-0019) | Children do not change the occupancy rate (1 adult + 1 child pays the single rate). Confirm with the hotel; changing it is a one-line rule in `availability.quote` | Hotel |
| GitHub push pending | Repository created; push blocked because the signed-in GitHub account lacks write access. Needs the owner account to push, or collaborator access | Project owner |
| Razorpay keys | Staging uses test payments; live/test keys to be entered in Admin > Payment gateway | Hotel |
| Email (SMTP) | Not configured; confirmation and password-reset emails are logged, not sent | Hotel / IT |
| Placeholder content | Site settings still contain `[bracketed]` placeholders (e.g. "State and PIN" not yet saved, cancellation policy) | Hotel |
| Settings page UX | Unsaved per-field edits are easy to miss (no unsaved-changes warning) — proposed, not implemented | Development |
| Python 3.10 on host | 3.10 reaches end of security support this month; request 3.11+ from the host | Hosting |
| Audit triggers on staging | Not installed (no SUPER); append-only relies on account grants there | Hosting / Development |
| Office IP whitelist | Ask the host to whitelist the office IP blocked on 2026-10-24 | IT |
