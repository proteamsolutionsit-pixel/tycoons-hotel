"""Test payment mode (PAYMENT_MODE=mock) - for development and demos without a
Razorpay account. NEVER available in production (config refuses to start).

It replaces only the calls that would go to Razorpay's servers. Everything
else runs the real code path: server-side order and price, room hold,
HMAC signature verification in /payments/verify, the payment state machine,
admin refunds/reconcile and the audit log.

"Razorpay's" side of each simulated payment is persisted as a payment_events
row (source="mock"), so verification keeps working across API restarts.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from sqlalchemy import select

from app.services.razorpay_gateway import GatewayError

# Fixed, public test keys: mock mode is dev-only and refused in production,
# so these protect nothing real. They exist so the real HMAC checks run.
MOCK_KEY_ID = "rzp_test_mock"
MOCK_KEY_SECRET = "mock-mode-key-secret-not-for-production"  # noqa: S105  # pragma: allowlist secret
MOCK_WEBHOOK_SECRET = "mock-mode-webhook-secret-not-for-production"  # noqa: S105  # pragma: allowlist secret


def _hmac(secret: str, message: str | bytes) -> str:
    msg = message.encode() if isinstance(message, str) else message
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class MockGateway:
    key_id = MOCK_KEY_ID
    mode = "mock"

    # -- "Razorpay API" ------------------------------------------------------
    def create_order(self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
        return {"id": "order_mock" + secrets.token_hex(7), "amount": amount, "currency": currency,
                "receipt": receipt, "notes": notes, "status": "created"}

    @staticmethod
    def _attempts(**where) -> list[dict[str, Any]]:
        from app.db.session import SessionLocal
        from app.models import PaymentEvent

        with SessionLocal() as db:
            stmt = select(PaymentEvent).where(PaymentEvent.source == "mock")
            for col, value in where.items():
                stmt = stmt.where(getattr(PaymentEvent, col) == value)
            return [dict(e.payload) for e in db.execute(stmt.order_by(PaymentEvent.id)).scalars()]

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        found = self._attempts(razorpay_payment_id=payment_id)
        if not found:
            raise GatewayError("payment.fetch")
        return found[-1]

    def fetch_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        return self._attempts(razorpay_order_id=order_id)

    def capture_payment(self, payment_id: str, amount: int, currency: str) -> dict[str, Any]:
        return {**self.fetch_payment(payment_id), "status": "captured"}

    def refund_payment(self, payment_id: str, amount: int, notes: dict[str, str]) -> dict[str, Any]:
        return {"id": "rfnd_mock" + secrets.token_hex(6), "payment_id": payment_id, "amount": amount,
                "status": "processed"}

    # -- signatures: the same HMAC-SHA256 scheme Razorpay uses ----------------
    @staticmethod
    def sign(order_id: str, payment_id: str) -> str:
        return _hmac(MOCK_KEY_SECRET, f"{order_id}|{payment_id}")

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return hmac.compare_digest(self.sign(order_id, payment_id), signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return bool(signature) and hmac.compare_digest(_hmac(MOCK_WEBHOOK_SECRET, raw_body), signature)


mock_gateway = MockGateway()
