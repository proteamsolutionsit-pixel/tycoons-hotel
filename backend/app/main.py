"""FastAPI application entry point: `uvicorn app.main:app`.

The schema is managed by Alembic only - nothing here creates or alters
tables. Run `alembic upgrade head` as a deployment step."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import API_PREFIX, api_router, legacy_api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import DatabaseLimiter
from app.core.security import CSRF_HEADER
from app.core.timeutil import utcnow
from app.db.session import SessionLocal, engine
from app.middleware.request_context import BodySizeLimitMiddleware, RequestContextMiddleware
from app.repositories.bookings import expire_stale_holds

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
log = logging.getLogger("app")
# Created at import, not only in lifespan: under Passenger (WSGI via a2wsgi)
# the ASGI lifespan never runs. Housekeeping then runs from cron
# (`python -m app.cli housekeeping`).
(settings.storage_dir / "public").mkdir(parents=True, exist_ok=True)
(settings.storage_dir / "private").mkdir(parents=True, exist_ok=True)


def _housekeeping() -> None:
    with SessionLocal() as db:
        n = expire_stale_holds(db, utcnow())
        db.commit()
    if n:
        log.info("Expired lapsed booking holds", extra={"count": n})
    if settings.rate_limit_backend == "database":
        DatabaseLimiter.purge_expired()


async def _housekeeper() -> None:
    """Every minute: release lapsed booking holds, purge old rate-limit rows.
    Safe to run on several instances at once (both are idempotent updates)."""
    while True:
        try:
            await run_in_threadpool(_housekeeping)
        except Exception:
            log.exception("Housekeeping failed")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_housekeeper()) if settings.environment != "test" else None
    if settings.payment_mode == "mock":
        log.warning("PAYMENT_MODE=mock: TEST PAYMENTS ONLY - no real money moves (development only)")
    elif not settings.razorpay_configured:
        log.warning("Razorpay keys are not set: online booking payments are disabled")
    log.info("Startup complete", extra={"environment": settings.environment})
    yield
    # Graceful shutdown: uvicorn stops accepting requests and lets in-flight
    # ones finish before this runs.
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    engine.dispose()
    log.info("Shutdown complete")


# Interactive docs are a development aid; on staging/production they would publish the full API map
_docs = settings.environment in ("development", "test")

app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description=(
        "REST API for The Tycoons Hotel website: content, room availability and bookings with Razorpay payments, "
        "guest request forms, and the staff admin.\n\n"
        f"All endpoints are under `{API_PREFIX}`. Errors use one envelope: "
        "`{\"error\": {\"code\", \"message\", \"details\"?, \"request_id\"}}` - 4xx codes are business/validation "
        "errors safe to show to users, 5xx are server faults. Money is integer paise (INR); dates are hotel-local "
        "(Asia/Kolkata) `YYYY-MM-DD`; timestamps are UTC ISO-8601."
    ),
    lifespan=lifespan,
    docs_url=f"{API_PREFIX}/docs" if _docs else None,
    redoc_url=f"{API_PREFIX}/redoc" if _docs else None,
    openapi_url=f"{API_PREFIX}/openapi.json" if _docs else None,
)

# Middleware runs outermost-last-added: request context -> host check -> body size -> CORS -> app
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key", CSRF_HEADER, "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)
app.add_middleware(BodySizeLimitMiddleware)
if "*" not in settings.allowed_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(RequestContextMiddleware)
register_error_handlers(app)
app.include_router(api_router)
app.include_router(legacy_api_router)

# Admin-uploaded images. CVs live in storage/private and are never mounted.
app.mount(settings.media_url_prefix, StaticFiles(directory=settings.storage_dir / "public", check_dir=False),
          name="media")

# Optional: serve the built React app (history-API fallback to index.html).
if settings.frontend_dist:
    dist = settings.frontend_dist.resolve()
    if (dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise StarletteHTTPException(status_code=404, detail="Not found")
            candidate = (dist / full_path).resolve()
            if full_path and dist in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
