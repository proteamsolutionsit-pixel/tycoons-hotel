"""Pure-ASGI middleware (streaming responses and the raw webhook body are
untouched): request id + access log + security headers, and a request-body
size limit enforced before any handler or multipart parser runs."""
from __future__ import annotations

import contextlib
import json
import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

log = logging.getLogger("app.access")
_RID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
LEGACY_PREFIX = "/api/"
CURRENT_PREFIX = "/api/v1/"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.hsts = get_settings().environment == "production"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _RID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid
        start = time.perf_counter()
        status = {"code": 500}
        path = scope.get("path", "")
        legacy = path.startswith(LEGACY_PREFIX) and not path.startswith(CURRENT_PREFIX)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = rid
                for k, v in SECURITY_HEADERS.items():
                    headers.setdefault(k, v)
                if self.hsts:
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
                if path.startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
                if legacy:
                    # Unversioned paths still work; tell clients where to go.
                    headers["Deprecation"] = "true"
                    headers["Link"] = f'<{CURRENT_PREFIX}{path[len(LEGACY_PREFIX):]}>; rel="successor-version"'
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info("request", extra={
                "request_id": rid, "method": scope.get("method"), "path": path, "status": status["code"],
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "admin_id": (scope.get("state") or {}).get("admin_id"),
            })


class BodySizeLimitMiddleware:
    """413 for bodies over the limit: multipart (uploads) and everything else
    have separate limits. Checks Content-Length up front and also counts the
    bytes actually received, so chunked requests can't bypass it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        s = get_settings()
        self.json_limit = s.max_json_body_bytes
        self.upload_limit = s.max_upload_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        ctype = headers.get(b"content-type", b"").decode("latin-1").lower()
        limit = self.upload_limit if ctype.startswith("multipart/form-data") else self.json_limit
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    await self._reject(scope, send, limit)
                    return
            except ValueError:
                await self._reject(scope, send, limit, status=400)
                return

        received = 0
        too_big = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, too_big
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_big = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            # FastAPI turns errors raised while parsing a body into its own 400;
            # once we know the body was oversized, replace that with a 413.
            if too_big:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        with contextlib.suppress(_BodyTooLarge):
            await self.app(scope, limited_receive, guarded_send)
        if too_big and not started:
            await self._reject(scope, send, limit)

    @staticmethod
    async def _reject(scope: Scope, send: Send, limit: int, status: int = 413) -> None:
        msg = (f"The request is too large (limit {limit // (1024 * 1024) or 1} MB)." if status == 413
               else "Invalid Content-Length.")
        body = json.dumps({"error": {"code": "request_too_large" if status == 413 else "bad_request",
                                     "message": msg,
                                     "request_id": (scope.get("state") or {}).get("request_id")}}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})


class _BodyTooLarge(Exception):
    pass
