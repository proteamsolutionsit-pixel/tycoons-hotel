"""Small sliding-window rate limiter for sensitive endpoints.

State is per process. That is enough for a single uvicorn worker; with several
workers or hosts, back this with Redis (same interface) — see README.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import TooManyRequests


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> int | None:
        """Record a hit. Returns None if allowed, else seconds until a slot frees."""
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


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers --forwarded-allow-ips=<proxy> rewrites client.host
    # from X-Forwarded-For when behind a trusted reverse proxy.
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int, window: int):
    """FastAPI dependency: limit requests per client IP for a named scope."""

    def _dep(request: Request) -> None:
        enforce(request, scope, limit, window)

    return _dep


def enforce(request: Request, scope: str, limit: int, window: int, extra_key: str = "") -> None:
    if not get_settings().rate_limit_enabled:
        return
    retry = limiter.hit(f"{scope}:{client_ip(request)}:{extra_key}", limit, window)
    if retry is not None:
        raise TooManyRequests(
            f"Too many attempts. Please try again in {retry} seconds.",
            headers={"Retry-After": str(retry)},
        )
