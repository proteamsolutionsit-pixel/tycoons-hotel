from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def make_engine(url: str | None = None) -> Engine:
    s = get_settings()
    engine = create_engine(
        url or s.database_url,
        echo=s.database_echo,
        pool_pre_ping=True,
        pool_recycle=1800,
        # READ COMMITTED: each statement sees the latest committed rows. The
        # booking/payment code re-checks inventory after taking row locks, and
        # under MySQL's default REPEATABLE READ a plain SELECT could still read
        # an older snapshot. Critical sections are serialised by FOR UPDATE.
        isolation_level="READ COMMITTED",
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _utc_session(dbapi_conn, _record):  # every timestamp in and out is UTC
        with dbapi_conn.cursor() as cur:
            cur.execute("SET time_zone = '+00:00'")

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
