"""Management commands.

    python -m app.cli seed                       # load initial content (idempotent)
    python -m app.cli create-admin --email a@b.c --name "Jane Doe" [--role admin|staff]
    python -m app.cli reconcile [--older-than 10]  # re-check unpaid orders with Razorpay
    python -m app.cli expire-holds               # release lapsed booking holds
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import timedelta

from sqlalchemy import func, select

from app.core.security import hash_password, password_problems
from app.core.timeutil import utcnow
from app.db.session import SessionLocal
from app.models import AdminUser, Booking, Payment
from app.models.enums import AdminRole, BookingStatus, PaymentStatus
from app.repositories.bookings import expire_stale_holds
from app.seed import seed
from app.services import payment_service
from app.services.auth_service import revoke_all
from app.services.razorpay_gateway import get_gateway


def cmd_seed(_args) -> int:
    with SessionLocal() as db:
        added = seed(db)
    print("Seeded:", added or "nothing new")
    return 0


def cmd_create_admin(args) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (12+ chars, upper, lower, digit): ")
    if problems := password_problems(password):
        print("Password needs " + ", ".join(problems), file=sys.stderr)
        return 1
    email = args.email.strip().lower()
    with SessionLocal() as db:
        user = db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email)).scalar_one_or_none()
        if user:
            user.password_hash = hash_password(password)
            user.role = AdminRole(args.role)
            user.is_active = True
            revoke_all(db, user.id, "password_reset_cli")
            action = "Updated"
        else:
            db.add(AdminUser(email=email, full_name=args.name, role=AdminRole(args.role),
                             password_hash=hash_password(password), is_active=True))
            action = "Created"
        db.commit()
    print(f"{action} {args.role} {email}")
    return 0


def cmd_reconcile(args) -> int:
    gateway = get_gateway()
    if gateway is None:
        print("Razorpay keys are not configured.", file=sys.stderr)
        return 1
    cutoff = utcnow() - timedelta(minutes=args.older_than)
    with SessionLocal() as db:
        ids = db.execute(select(Payment.id).join(Booking, Payment.booking_id == Booking.id).where(
            Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.AUTHORIZED, PaymentStatus.FAILED]),
            Booking.status.in_([BookingStatus.PENDING_PAYMENT, BookingStatus.EXPIRED]),
            Payment.created_at <= cutoff,
            Payment.created_at >= utcnow() - timedelta(days=7),
        )).scalars().all()
    for pid in ids:
        with SessionLocal() as db:
            try:
                out = payment_service.reconcile(db, pid, gateway)
                b = out.confirmed_booking
                print(f"payment {pid}: {b.reference} -> {b.status.value} {out.notes}")
            except Exception as exc:  # keep going through the list
                print(f"payment {pid}: failed ({exc})", file=sys.stderr)
    print(f"Checked {len(ids)} payment(s).")
    return 0


def cmd_expire(_args) -> int:
    with SessionLocal() as db:
        n = expire_stale_holds(db, utcnow())
        db.commit()
    print(f"Expired {n} hold(s).")
    return 0


def cmd_housekeeping(_args) -> int:
    """What the API's background loop does under uvicorn; run from cron where
    the app is hosted under Passenger (no ASGI lifespan)."""
    from app.core.config import get_settings
    from app.core.rate_limit import DatabaseLimiter

    with SessionLocal() as db:
        n = expire_stale_holds(db, utcnow())
        db.commit()
    purged = DatabaseLimiter.purge_expired() if get_settings().rate_limit_backend == "database" else 0
    print(f"Expired {n} hold(s); purged {purged} rate-limit row(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed").set_defaults(fn=cmd_seed)
    ca = sub.add_parser("create-admin", help="Create or reset a staff account (password from ADMIN_PASSWORD or prompt)")
    ca.add_argument("--email", required=True)
    ca.add_argument("--name", default="Administrator")
    ca.add_argument("--role", choices=[r.value for r in AdminRole], default="admin")
    ca.set_defaults(fn=cmd_create_admin)
    rc = sub.add_parser("reconcile")
    rc.add_argument("--older-than", type=int, default=10, help="minutes")
    rc.set_defaults(fn=cmd_reconcile)
    sub.add_parser("expire-holds").set_defaults(fn=cmd_expire)
    sub.add_parser("housekeeping", help="Expire lapsed holds and purge old rate-limit rows (for cron)") \
        .set_defaults(fn=cmd_housekeeping)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
