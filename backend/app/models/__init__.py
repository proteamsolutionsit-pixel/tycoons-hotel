"""Import every model so Base.metadata is complete (Alembic, tests)."""
from app.models.admin_user import AdminUser
from app.models.booking import Booking
from app.models.content import ContentCard, GalleryImage, JobOpening, SiteSetting, SpaTreatment
from app.models.payment import Payment, PaymentEvent
from app.models.room import RoomType
from app.models.submissions import (Enquiry, JobApplication, NewsletterSubscriber, SpaAppointment,
                                    TableReservation)

__all__ = [
    "AdminUser", "Booking", "ContentCard", "Enquiry", "GalleryImage", "JobApplication", "JobOpening",
    "NewsletterSubscriber", "Payment", "PaymentEvent", "RoomType", "SiteSetting", "SpaAppointment",
    "SpaTreatment", "TableReservation",
]
