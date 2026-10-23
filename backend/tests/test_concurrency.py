"""Parallel checkouts must never oversell: the room-type row lock serialises
the inventory check and the insert."""
from concurrent.futures import ThreadPoolExecutor

from app.core.errors import Conflict
from app.db.session import SessionLocal
from app.models import Booking
from app.models.enums import BookingStatus
from app.schemas.booking import BookingCreate
from app.services import booking_service
from tests.conftest import booking_payload


def test_parallel_checkouts_do_not_oversell(gateway, db):
    def attempt(i: int) -> str:
        data = BookingCreate(**booking_payload(room="tycoon-suite", guest_email=f"guest{i}@example.com"))
        with SessionLocal() as s:
            try:
                booking_service.create_booking(s, data, None, gateway)
                return "ok"
            except Conflict as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    assert results.count("ok") == 2, results          # the suite has 2 rooms
    assert results.count("sold_out") == 4, results
    assert db.query(Booking).filter(Booking.status == BookingStatus.PENDING_PAYMENT).count() == 2
