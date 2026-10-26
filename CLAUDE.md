# The Tycoons Hotel — working rules

## CHANGELOG.md is mandatory

Every modification to this project — frontend, backend, database/migrations, auth/RBAC, security,
configuration, API, dependencies, logging, deployment — gets an entry in [CHANGELOG.md](CHANGELOG.md)
**as part of the same task**, before reporting the task done:

1. Add a `CHG-NNNN` entry at the top of *Change history* (next free ID; newest first) with: date, module,
   change type, environment, status, commit, reason, previous/new behaviour, files actually modified,
   security/database/API/configuration impact, tests actually run and their real results, deployment notes,
   rollback plan.
2. Update the matching registers: *Security changes* (`SEC-`), *Bug fix* (`BUG-`), *Feature* (`FEAT-`),
   *Database*, *API*, *Configuration*, *Dependency*, and the *Deployment and release log* (`REL-`) when deployed.
3. Never rewrite or delete history; only correct inaccurate entries, saying so.
4. Evidence only: unknown → *Not provided*, unchecked → *Not verified*. Never call a vulnerability fixed without verification.
5. Never write secrets (passwords, OTPs, keys, tokens, DB credentials) — name config keys, never values.
6. In the final reply: what changed, files modified, security implications, tests and results, that
   CHANGELOG.md was updated, outstanding risks.

## Deploying to staging (devtycoonshotel.proteam.co.in)

See [docs/OPERATIONS.md](docs/OPERATIONS.md). Order: back up the database → run the migration (`migrate.py`)
→ upload the release (`scripts/build-release.ps1`) → restart → live check → remove temporary files and
one-off cron jobs. Keep cPanel API calls few; the host firewall blocks IPs after heavy use.
