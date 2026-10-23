from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import make_engine
import app.models  # noqa: F401  (registers every table on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # `alembic -x url=...` overrides DATABASE_URL (used by the test suite)
    # MIGRATION_DATABASE_URL (schema owner) when set; the runtime account has DML rights only.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().migration_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      compare_type=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
