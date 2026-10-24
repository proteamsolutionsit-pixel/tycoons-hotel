"""Thin wrapper around the official Razorpay Python SDK.

Everything that talks to Razorpay goes through this class so tests can swap
in a fake, and so SDK/network errors surface as one exception type.
"""
from __future__ import annotations

import hashlib
import logging
import warnings
from typing import Any, Protocol

with warnings.catch_warnings():
    # razorpay 1.4.2 imports pkg_resources (needs setuptools, pinned in requirements)
    warnings.simplefilter("ignore", UserWarning)
    import razorpay
from fastapi import Depends
from razorpay.errors import SignatureVerificationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services import payment_settings_service
from app.services.payment_settings_service import GatewayConfig

log = logging.getLogger("app.razorpay")


class GatewayError(Exception):
    pass


class PaymentGateway(Protocol):
    key_id: str

    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]: ...
    def fetch_payment(self, payment_id: str) -> dict[str, Any]: ...
    def fetch_order_payments(self, order_id: str) -> list[dict[str, Any]]: ...
    def capture_payment(self, payment_id: str, amount: int, currency: str) -> dict[str, Any]: ...
    def refund_payment(self, payment_id: str, amount: int, notes: dict[str, str]) -> dict[str, Any]: ...
    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class RazorpayGateway:
    mode = "razorpay"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str, timeout: int = 15):
        self.key_id = key_id
        self._webhook_secret = webhook_secret
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._timeout = timeout
        self._client.set_app_details({"title": "The Tycoons Hotel", "version": "1.0"})

    # -- API calls --------------------------------------------------------
    def _call(self, what: str, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs, timeout=self._timeout)
        except Exception as exc:  # SDK raises several types incl. requests errors
            log.warning("Razorpay %s failed: %s", what, exc.__class__.__name__,
                        extra={"razorpay_error": str(exc)[:300]})
            raise GatewayError(what) from exc

    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
        return self._call("order.create", self._client.order.create,
                          data={"amount": amount, "currency": currency, "receipt": receipt, "notes": notes})

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self._call("payment.fetch", self._client.payment.fetch, payment_id)

    def fetch_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        res = self._call("order.payments", self._client.order.payments, order_id)
        return list(res.get("items", []))

    def capture_payment(self, payment_id: str, amount: int, currency: str) -> dict[str, Any]:
        return self._call("payment.capture", self._client.payment.capture, payment_id, amount,
                          data={"currency": currency})

    def refund_payment(self, payment_id: str, amount: int, notes: dict[str, str]) -> dict[str, Any]:
        return self._call("payment.refund", self._client.payment.refund, payment_id,
                          data={"amount": amount, "speed": "normal", "notes": notes})

    def check_credentials(self) -> None:
        """Cheapest authenticated call: raises GatewayError if the keys are refused."""
        self._call("order.all", self._client.order.all, data={"count": 1})

    # -- signatures (HMAC-SHA256, verified by the SDK) -------------------
    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        try:
            self._client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
            return True
        except SignatureVerificationError:
            return False

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        if not self._webhook_secret or not signature:
            return False
        try:
            body = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            return False
        try:
            self._client.utility.verify_webhook_signature(body, signature, self._webhook_secret)
            return True
        except SignatureVerificationError:
            return False


_cache: dict[tuple, RazorpayGateway] = {}


def gateway_for(cfg: GatewayConfig) -> PaymentGateway | None:
    """The gateway for a configuration: the mock one in test-payment mode (never
    in production), Razorpay when keys are set, otherwise None (payments off)."""
    s = get_settings()
    if cfg.mode == "mock":
        if s.environment == "production":
            return None
        from app.services.mock_gateway import mock_gateway
        return mock_gateway
    if not (cfg.key_id and cfg.key_secret):
        return None
    # One client per distinct key set; hashes keep secrets out of the cache key
    key = (cfg.key_id, _digest(cfg.key_secret), _digest(cfg.webhook_secret), s.razorpay_timeout_seconds)
    gw = _cache.get(key)
    if gw is None:
        _cache.clear()
        gw = _cache[key] = RazorpayGateway(cfg.key_id, cfg.key_secret, cfg.webhook_secret, s.razorpay_timeout_seconds)
    return gw


def get_gateway(db: Session = Depends(get_db)) -> PaymentGateway | None:
    """FastAPI dependency: the gateway for the configuration in force right now
    (Admin > Payment gateway, else the environment)."""
    return gateway_for(payment_settings_service.load(db))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
