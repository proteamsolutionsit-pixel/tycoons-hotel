"""Rate limiting for sensitive and expensive endpoints.

Two backends behind one interface:
* database (default) - fixed-window counters in MySQL (`rate_limit_buckets`),
  shared by every worker and host, so limits hold when the API is scaled out.
  One atomic INSERT ... ON DUPLICATE KEY UPDATE per hit.
* memory - per-process sliding window; for tests and single-process tools.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import cast

from fastapi import Request
from sqlalchemy import Table, case, delete, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.core.config import get_settings
from app.core.errors import TooManyRequests
from app.core.timeutil import utcnow


class MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> int | None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(q[0] + window - now) + 1)
            q.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class DatabaseLimiter:
    """Window starts at the first hit for a key and lasts `window` seconds."""

    def hit(self, key: str, limit: int, window: int) -> int | None:
        from app.db.session import engine
        from app.models import RateLimitBucket

        t = cast(Table, RateLimitBucket.__table__)
        bucket = hashlib.sha256(key.encode("utf-8")).hexdigest()
        now = utcnow().replace(microsecond=0)
        new_expiry = now + timedelta(seconds=window)
        stmt = mysql_insert(t).values(bucket_key=bucket, hits=1, expires_at=new_expiry)
        # MySQL evaluates these left to right: `hits` is computed against the
        # old expires_at before expires_at itself is reset.
        stmt = stmt.on_duplicate_key_update(
            hits=case((t.c.expires_at <= now, 1), else_=t.c.hits + 1),
            expires_at=case((t.c.expires_at <= now, new_expiry), else_=t.c.expires_at),
        )
        with engine.begin() as conn:
            conn.execute(stmt)
            hits, expires_at = conn.execute(
                select(t.c.hits, t.c.expires_at).where(t.c.bucket_key == bucket)).one()
        if hits > limit:
            return max(1, int((expires_at - now).total_seconds()))
        return None

    def reset(self) -> None:
        from app.db.session import engine
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_buckets"))

    @staticmethod
    def purge_expired() -> int:
        from app.db.session import engine
        from app.models import RateLimitBucket
        with engine.begin() as conn:
            return conn.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < utcnow())).rowcount or 0


_memory = MemoryLimiter()
_database = DatabaseLimiter()


class _Limiter:
    """Facade choosing the configured backend at call time."""

    @property
    def backend(self):
        return _database if get_settings().rate_limit_backend == "database" else _memory

    def hit(self, key: str, limit: int, window: int) -> int | None:
        return self.backend.hit(key, limit, window)

    def reset(self) -> None:
        _memory.reset()
        if get_settings().rate_limit_backend == "database":
            _database.reset()


limiter = _Limiter()


def client_ip(request: Request) -> str:
    # Behind nginx, uvicorn --proxy-headers --forwarded-allow-ips=<proxy> sets
    # client.host from X-Forwarded-For; untrusted clients cannot spoof it.
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int, window: int):
    """FastAPI dependency: limit requests per client IP for a named scope."""

    def _dep(request: Request) -> None:
        enforce(request, scope, limit, window)

    return _dep


def enforce(request: Request, scope: str, limit: int, window: int, extra_key: str = "",
            per_ip: bool = True) -> None:
    if not get_settings().rate_limit_enabled:
        return
    ident = (client_ip(request) if per_ip else "*") + ":" + extra_key
    retry = limiter.hit(f"{scope}|{ident}", limit, window)
    if retry is not None:
        raise TooManyRequests(
            f"Too many attempts. Please try again in {retry} seconds.",
            headers={"Retry-After": str(retry)},
        )
