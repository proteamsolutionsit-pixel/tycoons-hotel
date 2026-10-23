"""Thin wrapper around the official Razorpay Python SDK.

Everything that talks to Razorpay goes through this class so tests can swap
in a fake, and so SDK/network errors surface as one exception type.
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Protocol

with warnings.catch_warnings():
    # razorpay 1.4.2 imports pkg_resources (needs setuptools, pinned in requirements)
    warnings.simplefilter("ignore", UserWarning)
    import razorpay
from razorpay.errors import SignatureVerificationError

from app.core.config import get_settings

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


_gateway: RazorpayGateway | None = None


def get_gateway() -> PaymentGateway | None:
    """FastAPI dependency. None when Razorpay keys are not configured."""
    global _gateway
    s = get_settings()
    if not s.razorpay_configured:
        return None
    if _gateway is None:
        _gateway = RazorpayGateway(s.razorpay_key_id, s.razorpay_key_secret, s.razorpay_webhook_secret,
                                   s.razorpay_timeout_seconds)
    return _gateway
