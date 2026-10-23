from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Payment, PaymentEvent


def get_by_order_id(db: Session, order_id: str, *, for_update: bool = False) -> Payment | None:
    stmt = select(Payment).where(Payment.razorpay_order_id == order_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.execute(stmt).scalar_one_or_none()


def lock(db: Session, payment_id: int) -> Payment:
    return db.execute(select(Payment).where(Payment.id == payment_id).with_for_update()
                      .execution_options(populate_existing=True)).scalar_one()


def record_event(db: Session, *, source: str, event_type: str, payload: Any, order_id: str | None = None,
                 payment_id: str | None = None, event_id: str | None = None,
                 result: str | None = None) -> PaymentEvent | None:
    """Insert an audit event. With an event_id, returns None if that event was
    already recorded (duplicate webhook delivery)."""
    ev = PaymentEvent(event_id=event_id, source=source, event_type=event_type, payload=payload,
                      razorpay_order_id=order_id, razorpay_payment_id=payment_id, result=result)
    if event_id is None:
        db.add(ev)
        db.flush()
        return ev
    try:
        with db.begin_nested():
            db.add(ev)
            db.flush()
    except IntegrityError:
        return None
    return ev
