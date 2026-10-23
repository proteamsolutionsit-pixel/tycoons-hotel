"""FastAPI application entry point: `uvicorn app.main:app`."""
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

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.security import CSRF_HEADER
from app.core.timeutil import utcnow
from app.db.session import SessionLocal
from app.middleware.request_context import RequestContextMiddleware
from app.repositories.bookings import expire_stale_holds

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
log = logging.getLogger("app")


def _expire_holds_once() -> int:
    with SessionLocal() as db:
        n = expire_stale_holds(db, utcnow())
        db.commit()
        return n


async def _hold_sweeper() -> None:
    """Release lapsed booking holds every minute (lookups also do it lazily)."""
    while True:
        try:
            n = await run_in_threadpool(_expire_holds_once)
            if n:
                log.info("Expired lapsed booking holds", extra={"count": n})
        except Exception:
            log.exception("Hold sweeper failed")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    (settings.storage_dir / "public").mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "private").mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_hold_sweeper()) if settings.environment != "test" else None
    if not settings.razorpay_configured:
        log.warning("Razorpay keys are not set: online booking payments are disabled")
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="REST API for The Tycoons Hotel website: content, room availability and bookings with "
                "Razorpay payments, guest request forms, and the staff admin.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key", CSRF_HEADER, "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)
app.add_middleware(RequestContextMiddleware)
register_error_handlers(app)
app.include_router(api_router)

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
