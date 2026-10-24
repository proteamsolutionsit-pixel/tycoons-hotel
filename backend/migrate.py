"""Apply database migrations (alembic upgrade head) and print the result.

For hosts without a shell: cPanel > Setup Python App > Execute python script
> `migrate.py`. Uses MIGRATION_DATABASE_URL from .env (the schema owner).
Migrations are additive and already-applied ones are skipped, so running this
twice is harmless. Back up the database first."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import make_engine  # noqa: E402


def current_revision() -> str | None:
    engine = make_engine(get_settings().migration_url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def main() -> int:
    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    before = current_revision()
    print(f"database revision before: {before}, latest: {head}")
    if before == head:
        print("Already up to date. Nothing to do.")
        return 0
    command.upgrade(cfg, "head")
    after = current_revision()
    print(f"database revision after: {after}")
    print("OK - migration applied." if after == head else "WARNING - not at the latest revision.")
    return 0 if after == head else 1


if __name__ == "__main__":
    sys.exit(main())
