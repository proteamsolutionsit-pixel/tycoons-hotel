"""Admin > Payment gateway: test-payment mode or Razorpay, and the Razorpay keys.
Admin role only (payments.settings). Secrets go in, never come back out."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.permissions import Permission
from app.core.rate_limit import enforce
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.admin import PaymentSettingsOut, PaymentSettingsTest, PaymentSettingsTestResult, PaymentSettingsUpdate
from app.services import audit, payment_settings_service

router = APIRouter(prefix="/payment-settings", tags=["Admin: payment gateway"])
_PERM = Permission.PAYMENTS_SETTINGS


@router.get("", response_model=PaymentSettingsOut)
def get_settings(_: AdminUser = Depends(require(_PERM)), db: Session = Depends(get_db)):
    return payment_settings_service.public_view(db)


@router.put("", response_model=PaymentSettingsOut, summary="Change the payment mode or Razorpay keys")
def update_settings(data: PaymentSettingsUpdate, request: Request, actor: AdminUser = Depends(require(_PERM)),
                    db: Session = Depends(get_db)):
    return payment_settings_service.update(db, mode=data.mode, key_id=data.key_id, key_secret=data.key_secret,
                                           webhook_secret=data.webhook_secret, confirm_live=data.confirm_live,
                                           actor=actor, request=request)


@router.delete("", response_model=PaymentSettingsOut, summary="Go back to the server's environment settings")
def reset_settings(request: Request, actor: AdminUser = Depends(require(_PERM)), db: Session = Depends(get_db)):
    return payment_settings_service.reset(db, actor=actor, request=request)


@router.post("/test", response_model=PaymentSettingsTestResult, summary="Check Razorpay keys with one read-only call")
def test_settings(data: PaymentSettingsTest, request: Request, actor: AdminUser = Depends(require(_PERM)),
                  db: Session = Depends(get_db)):
    enforce(request, "payment-settings-test", 10, 600, extra_key=str(actor.id))
    ok, message = payment_settings_service.test_credentials(db, key_id=data.key_id, key_secret=data.key_secret)
    audit.record_now(action="payment_settings.test", outcome="success" if ok else "failure", actor=actor,
                     resource_type="payment_settings", resource_id="1", details={"key_id": data.key_id or None},
                     request=request)
    return PaymentSettingsTestResult(ok=ok, message=message)
