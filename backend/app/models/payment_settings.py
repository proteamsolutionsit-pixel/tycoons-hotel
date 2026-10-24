"""Payment gateway configuration entered in the admin (one row, id = 1).

When the row does not exist the application uses PAYMENT_MODE and the
RAZORPAY_* environment variables, exactly as before this table existed."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base


class PaymentGatewaySettings(Base):
    __tablename__ = "payment_gateway_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    mode: Mapped[str] = mapped_column(String(16))                 # "mock" | "razorpay"
    key_id: Mapped[str] = mapped_column(String(64), default="")   # public (it is sent to the browser)
    key_secret_enc: Mapped[str | None] = mapped_column(Text)      # Fernet token, see core/secretbox
    webhook_secret_enc: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
