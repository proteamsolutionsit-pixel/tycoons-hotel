"""Payment gateway configuration: what is in force, and admin changes to it.

Precedence: the row saved from Admin > Payment gateway, else PAYMENT_MODE and
the RAZORPAY_* environment variables. Secrets are stored encrypted
(core/secretbox) and never leave the server: the API reports only whether one
is set. Test payments are refused in production whatever the source.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core import secretbox
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import AdminUser, PaymentGatewaySettings
from app.services import audit

log = logging.getLogger("app.payment_settings")

ROW_ID = 1
KEY_ID_RE = re.compile(r"^rzp_(test|live)_[A-Za-z0-9]{8,32}$")   # what the admin form accepts
_KIND_RE = re.compile(r"^rzp_(test|live)_")


@dataclass(frozen=True)
class GatewayConfig:
    mode: str                 # "mock" | "razorpay"
    key_id: str
    key_secret: str
    webhook_secret: str
    source: str               # "admin" | "environment"
    secrets_readable: bool = True


def key_kind(key_id: str) -> str | None:
    m = _KIND_RE.match(key_id or "")
    return m.group(1) if m else None


def _row(db: Session) -> PaymentGatewaySettings | None:
    return db.get(PaymentGatewaySettings, ROW_ID)


def _decrypt(token: str | None) -> str:
    return secretbox.decrypt(token) if token else ""


def load(db: Session) -> GatewayConfig:
    row = _row(db)
    if row is None:
        s = get_settings()
        return GatewayConfig(s.payment_mode, s.razorpay_key_id, s.razorpay_key_secret, s.razorpay_webhook_secret,
                             "environment")
    try:
        return GatewayConfig(row.mode, row.key_id, _decrypt(row.key_secret_enc), _decrypt(row.webhook_secret_enc),
                             "admin")
    except secretbox.SecretUnavailable:
        # Wrong or lost encryption key: fail closed (payments off) rather than crash every request
        log.error("Stored Razorpay secrets cannot be decrypted; re-enter them in Admin > Payment gateway")
        return GatewayConfig(row.mode, row.key_id, "", "", "admin", secrets_readable=False)


def public_view(db: Session) -> dict[str, Any]:
    s = get_settings()
    cfg = load(db)
    row = _row(db)
    by = db.get(AdminUser, row.updated_by_id) if row and row.updated_by_id else None
    mock_blocked = s.environment == "production"
    if cfg.mode == "mock":
        active = "disabled" if mock_blocked else "mock"
    else:
        active = (key_kind(cfg.key_id) or "disabled") if cfg.key_secret else "disabled"
    return {
        "mode": cfg.mode,
        "active": active,                    # mock | test | live | disabled
        "source": cfg.source,
        "key_id": cfg.key_id,
        "key_kind": key_kind(cfg.key_id),
        "has_key_secret": bool(cfg.key_secret),
        "has_webhook_secret": bool(cfg.webhook_secret),
        "secrets_readable": cfg.secrets_readable,
        "environment": s.environment,
        "mock_allowed": not mock_blocked,
        "webhook_url": s.public_base_url.rstrip("/") + "/api/v1/payments/webhook",
        "updated_at": row.updated_at if row else None,
        "updated_by": by.email if by else None,
    }


def _bad(field: str, msg: str) -> None:
    raise AppError(msg, code="validation_error", status_code=422, details=[{"field": field, "message": msg}])


def update(db: Session, *, mode: str, key_id: str, key_secret: str | None, webhook_secret: str | None,
           confirm_live: bool, actor: AdminUser, request: Request) -> dict[str, Any]:
    """Blank secrets keep the stored ones (for the same key id)."""
    s = get_settings()
    current = load(db)
    key_id = (key_id or "").strip()
    key_secret = (key_secret or "").strip() or None
    webhook_secret = (webhook_secret or "").strip() or None

    if mode == "mock":
        if s.environment == "production":
            _bad("mode", "Test payments are not allowed on the production site.")
        new_key_id, new_secret, new_webhook = current.key_id, current.key_secret, current.webhook_secret
    else:
        kind = key_kind(key_id)
        if kind is None or not KEY_ID_RE.match(key_id):
            _bad("key_id", "Enter the Key Id from Razorpay (it starts with rzp_test_ or rzp_live_).")
        if key_secret is None:
            if key_id != current.key_id or not current.key_secret:
                _bad("key_secret", "Enter the Key Secret that belongs to this Key Id.")
            key_secret = current.key_secret
        elif not 8 <= len(key_secret) <= 128 or not key_secret.isascii() or any(c.isspace() for c in key_secret):
            _bad("key_secret", "That doesn't look like a Razorpay Key Secret.")
        if webhook_secret is None:
            if not current.webhook_secret:
                _bad("webhook_secret", "Enter a webhook secret (the same one you enter in Razorpay's webhook settings).")
            webhook_secret = current.webhook_secret
        elif not 12 <= len(webhook_secret) <= 128 or any(c.isspace() for c in webhook_secret):
            _bad("webhook_secret", "Use 12 to 128 characters, without spaces.")
        if kind == "live" and key_kind(current.key_id) != "live" and not confirm_live:
            _bad("confirm_live", "Live keys take real money. Confirm that you want to switch to live payments.")
        new_key_id, new_secret, new_webhook = key_id, key_secret, webhook_secret

    row = _row(db) or PaymentGatewaySettings(id=ROW_ID)
    row.mode = mode
    row.key_id = new_key_id or ""
    row.key_secret_enc = secretbox.encrypt(new_secret) if new_secret else None
    row.webhook_secret_enc = secretbox.encrypt(new_webhook) if new_webhook else None
    row.updated_by_id = actor.id
    db.add(row)
    # Details record what changed - never the secrets themselves
    audit.record(db, action="payment_settings.update", actor=actor, resource_type="payment_settings",
                 resource_id=str(ROW_ID), request=request, details={
                     "mode": {"from": current.mode, "to": mode},
                     "key_id": {"from": current.key_id, "to": row.key_id},
                     # (names avoid "secret": the audit redactor would mask the flags themselves)
                     "replaced": {"api_key": new_secret != current.key_secret,
                                  "webhook_key": new_webhook != current.webhook_secret},
                     "previous_source": current.source,
                 })
    db.commit()
    log.warning("Payment gateway settings changed", extra={"mode": mode, "key_kind": key_kind(row.key_id),
                                                           "admin_id": actor.id})
    return public_view(db)


def reset(db: Session, *, actor: AdminUser, request: Request) -> dict[str, Any]:
    """Forget the admin-entered configuration; the environment variables apply again."""
    row = _row(db)
    if row is not None:
        audit.record(db, action="payment_settings.reset", actor=actor, resource_type="payment_settings",
                     resource_id=str(ROW_ID), request=request, details={"mode": row.mode, "key_id": row.key_id})
        db.delete(row)
        db.commit()
    return public_view(db)


def test_credentials(db: Session, *, key_id: str | None, key_secret: str | None) -> tuple[bool, str]:
    """Make one read-only call to Razorpay with the given keys (or the saved ones)."""
    from razorpay.errors import BadRequestError

    from app.services.razorpay_gateway import GatewayError, RazorpayGateway

    current = load(db)
    key_id = (key_id or "").strip() or current.key_id
    key_secret = (key_secret or "").strip() or None
    if key_secret is None:
        if key_id != current.key_id or not current.key_secret:
            return False, "Enter the Key Secret for this Key Id to test it."
        key_secret = current.key_secret
    if key_kind(key_id) is None:
        return False, "Enter a Razorpay Key Id (rzp_test_… or rzp_live_…)."
    try:
        RazorpayGateway(key_id, key_secret, "", get_settings().razorpay_timeout_seconds).check_credentials()
    except GatewayError as exc:
        if isinstance(exc.__cause__, BadRequestError):
            return False, "Razorpay rejected these keys. Check the Key Id and Key Secret."
        return False, "Could not reach Razorpay from the server. Try again in a minute."
    return True, f"Connected to Razorpay ({key_kind(key_id)} mode)."
