from __future__ import annotations

import enum


class AdminRole(str, enum.Enum):
    ADMIN = "admin"   # everything, including rates, content, settings and users
    STAFF = "staff"   # bookings (read) and guest submissions


class BookingStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"  # inventory held until hold_expires_at
    CONFIRMED = "confirmed"              # payment captured and verified
    PAYMENT_REVIEW = "payment_review"    # money captured but the hold had lapsed and the room is gone: refund or rehouse
    CANCELLED = "cancelled"
    EXPIRED = "expired"                  # hold lapsed without a captured payment


class PaymentStatus(str, enum.Enum):
    CREATED = "created"            # Razorpay order exists, nothing paid yet
    AUTHORIZED = "authorized"      # signature verified / authorised, not yet captured
    CAPTURED = "captured"          # money captured - the only state that confirms a booking
    FAILED = "failed"              # last attempt failed; the guest may retry on the same order
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class SubmissionStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    CLOSED = "closed"


class EnquiryKind(str, enum.Enum):
    CONTACT = "contact"
    BUSINESS = "business"


class GuestType(str, enum.Enum):
    HOTEL_GUEST = "hotel_guest"
    VISITOR = "visitor"


class CardSection(str, enum.Enum):
    DINING_MENU = "dining_menu"      # Fishy Tales: "Three ways to dine"
    LOUNGE_SPACES = "lounge_spaces"  # Business Lounge: "Work, meet, host"
    CAREER_TEAMS = "career_teams"    # Careers: "Our teams"


class GalleryCategory(str, enum.Enum):
    ROOMS = "rooms"
    DINING = "dining"
    WELLNESS = "wellness"
    SPACES = "spaces"


class GalleryLayout(str, enum.Enum):
    NORMAL = "normal"
    LARGE = "large"   # 2x2 tile in the mosaic
    WIDE = "wide"     # 2x1 tile
