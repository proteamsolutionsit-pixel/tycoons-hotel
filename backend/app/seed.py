"""Initial content, transcribed from the original HTML design.

Bracketed values such as "[Street address]" are the design's own
placeholders, kept verbatim so the site renders exactly like the original
until staff replace them in the admin. Room RATES and INVENTORY are SAMPLE
values (the design has none) - set the real ones before taking bookings.

Idempotent: tables that already have rows, and settings that already exist,
are left alone.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ContentCard, GalleryImage, JobOpening, RoomType, SiteSetting, SpaTreatment
from app.models.enums import CardSection, GalleryCategory, GalleryLayout

log = logging.getLogger("app.seed")

IMG = "/assets/img/"

ROOM_FACTS = dict(size_label="[Room size · sq ft]", bed_label="[Bed type]", view_label="[View]",
                  occupancy_label="[Max occupancy]")

ROOMS = [
    dict(slug="twin-room", name="Twin Room", sort_order=1, image_url=IMG + "room-twin.jpg", image_alt="Twin Room",
         summary="Two beds, a work desk and quiet comfort for colleagues travelling together.",
         description="Two beds, a dedicated work desk and quiet comfort — ideal for colleagues travelling together.",
         base_rate_paise=650000, total_rooms=12),
    dict(slug="premium-room", name="Premium Room", sort_order=2, image_url=IMG + "room-premium.jpg",
         image_alt="Premium Room",
         summary="Plush bedding, refined interiors and premium amenities for the business traveller.",
         description="Our signature room. Plush bedding, refined interiors and premium amenities for the business "
                     "traveller.",
         base_rate_paise=750000, total_rooms=16),
    dict(slug="deluxe-room", name="Deluxe Room", sort_order=3, image_url=IMG + "room-deluxe.jpg",
         image_alt="Deluxe Room",
         summary="More space to unwind, with a lounge corner and elevated in-room touches.",
         description="More space to unwind, with a lounge corner and elevated in-room touches for longer stays.",
         base_rate_paise=950000, total_rooms=10),
    dict(slug="tycoon-suite", name="Tycoon Suite", sort_order=4, image_url=IMG + "room-suite.jpg",
         image_alt="Tycoon Suite", is_signature=True,
         summary="Separate living space and residential-style privacy — our finest address.",
         description="A separate living space and residential-style privacy. Our finest address in the hotel.",
         base_rate_paise=1600000, total_rooms=2),
]

TREATMENTS = [
    dict(slug="soothing-massage", name="Soothing Massages", form_label="Soothing Massage", sort_order=1,
         description="Skilled hands to release tension and ease the body after travel or a demanding day.",
         image_url=IMG + "spa-massage.jpg", image_alt="Massage therapy"),
    dict(slug="tailored-therapy", name="Tailored Therapies", form_label="Tailored Therapy", sort_order=2,
         description="Treatments shaped around how you feel today, chosen with your therapist.",
         image_url=IMG + "spa.jpg", image_alt="Tailored spa therapy"),
    dict(slug="wellness-ritual", name="Wellness Rituals", form_label="Wellness Ritual", sort_order=3,
         description="Restorative rituals that combine calm, warmth and care for deeper renewal.",
         image_url=IMG + "gal-spa.jpg", image_alt="Spa ritual with candles and oils"),
]

CARDS = [
    (CardSection.DINING_MENU, "Coastal Classics",
     "Time-honoured recipes from the coast, prepared with the day's freshest catch.",
     "dining-dish.jpg", "Coastal seafood dish", "[Signature dishes]"),
    (CardSection.DINING_MENU, "Contemporary Seafood",
     "Modern creations that reimagine the sea with bold, contemporary flavours.",
     "gal-restaurant.jpg", "Elegant table setting", "[Signature dishes]"),
    (CardSection.DINING_MENU, "Private Dining & Occasions",
     "Celebrations, family gatherings and client dinners, hosted with care.",
     "breakfast.jpg", "Breakfast pastries", "[Capacity · packages]"),
    (CardSection.LOUNGE_SPACES, "Business Lounge",
     "A calm setting for informal meetings, calls and working between appointments.",
     "lounge.jpg", "Business lounge seating", "[Capacity] · [Hours]"),
    (CardSection.LOUNGE_SPACES, "Client Dinners",
     "Host clients and teams at Fishy Tales, with private dining on request.",
     "gal-restaurant.jpg", "Private dining table", "[Capacity] · [Packages]"),
    (CardSection.CAREER_TEAMS, "Rooms & Guest Services",
     "Front office, guest relations and housekeeping — the people who make every stay feel easy.",
     "lobby-lounge.jpg", "Hotel lounge", None),
    (CardSection.CAREER_TEAMS, "Fishy Tales",
     "Kitchen and service roles at our coastal seafood restaurant.",
     "dining-dish.jpg", "Seafood dish at Fishy Tales", None),
    (CardSection.CAREER_TEAMS, "Kai Wellness Spa",
     "Therapist and spa reception roles for those who love the art of care.",
     "spa-massage.jpg", "Massage therapy", None),
]

R, D, W, S = GalleryCategory.ROOMS, GalleryCategory.DINING, GalleryCategory.WELLNESS, GalleryCategory.SPACES
L, WD, N = GalleryLayout.LARGE, GalleryLayout.WIDE, GalleryLayout.NORMAL
# (file, alt, category, layout, width, height, home_order or None) - mosaic order of the Gallery page
GALLERY = [
    ("hero-city.jpg", "City skyline at dusk", S, L, 1920, 1280, None),
    ("gal-suite.jpg", "Suite living area", R, N, 900, 600, 2),
    ("room-twin.jpg", "Twin room", R, N, 1000, 667, None),
    ("room-premium.jpg", "Premium room", R, N, 720, 470, None),
    ("room-deluxe.jpg", "Deluxe room", R, N, 720, 470, None),
    ("lounge.jpg", "Business lounge", S, WD, 1200, 800, None),
    ("room-suite.jpg", "Tycoon Suite", R, N, 720, 470, None),
    ("lobby-lounge.jpg", "Hotel lounge", S, N, 600, 417, None),
    ("dining-dish.jpg", "Fishy Tales dish", D, N, 1200, 800, None),
    ("gal-restaurant.jpg", "Restaurant table setting", D, N, 800, 522, 4),
    ("breakfast.jpg", "Pastries", D, N, 800, 800, None),
    ("spa.jpg", "Spa treatment", W, N, 800, 546, None),
    ("spa-massage.jpg", "Massage", W, N, 800, 546, None),
    ("spa-ritual.jpg", "Spa ritual", W, N, 800, 546, None),
    ("gal-spa.jpg", "Spa candles and oils", W, N, 800, 546, 3),
    ("gal-pool.jpg", "Indoor pool", W, N, 900, 600, 1),
]

# (key, value, label, group, help)
SETTINGS = [
    ("address_street", "[Street address]", "Street address", "contact", "Shown in the header, menu, footer and Contact page"),
    ("address_city", "Bengaluru", "City", "contact", None),
    ("address_region_pin", "Karnataka [PIN]", "State and PIN", "contact", None),
    ("phone_display", "[+91 Phone]", "Reservations phone (as shown)", "contact", None),
    ("phone_tel", "+910000000000", "Reservations phone (dialled)", "contact", "Digits with country code, e.g. +918012345678"),
    ("landline_numbers", [{"label": "Reception", "value": "[Landline number]"}], "Landline numbers", "contact",
     "One row per number: a label (e.g. Reception, Front office) and the number with its STD code, e.g. 080 4123 4567. "
     "Shown in the footer and on the Contact page."),
    ("reservations_email_display", "[Reservations email]", "Reservations email (as shown)", "contact", None),
    ("reservations_email", "reservations@example.com", "Reservations email (address)", "contact", None),
    ("dining_phone_display", "[+91 Phone]", "Fishy Tales phone", "contact", None),
    ("spa_phone_display", "[+91 Phone]", "Kai Wellness Spa phone", "contact", None),
    ("careers_email_display", "[Careers email]", "Careers email", "contact", None),
    ("instagram_url", "https://instagram.com", "Instagram link", "social", None),
    ("facebook_url", "https://facebook.com", "Facebook link", "social", None),
    ("linkedin_url", "https://linkedin.com", "LinkedIn link", "social", None),
    ("amenities", ["Fishy Tales", "Kai Wellness Spa", "Business Lounge", "[Airport transfers]", "[Wi-Fi]"],
     "Amenities ticker (homepage)", "home", None),
    ("lounge_facts", ["[Wi-Fi details]", "[Airport transfer · distance]"], "Business lounge facts (homepage)", "home", None),
    ("stay_details", [{"label": "Check-in", "value": "[TIME]"}, {"label": "Check-out", "value": "[TIME]"},
                      {"label": "Breakfast", "value": "[Included / add-on]"}, {"label": "Parking", "value": "[Details]"}],
     "Stay details strip (Rooms page)", "rooms", None),
    ("room_tax_percent", 0, "Room tax (GST) %", "rooms",
     "Added to every online booking. Confirm the applicable GST slab with your accountant."),
    ("cancellation_policy", "[Cancellation policy]", "Cancellation policy (shown at checkout)", "rooms",
     "Shown to guests before they pay and saved with every booking as the terms they agreed to."),
    ("booking_terms_version", "2026-10", "Booking terms version", "rooms",
     "Change this whenever the policy text changes, so each booking records which version was accepted."),
    ("dining_details", [{"label": "Lunch", "value": "[HOURS]"}, {"label": "Dinner", "value": "[HOURS]"},
                        {"label": "Dress code", "value": "[Smart casual]"}, {"label": "Reservations", "value": "[+91 Phone]"}],
     "Restaurant details strip", "dining", None),
    ("dining_menu_pdf_url", "", "Menu PDF link", "dining", "Leave empty to keep the 'Download menu [PDF]' link pointing at the reservation form"),
    ("spa_details", [{"label": "Open", "value": "[HOURS]"}, {"label": "Booking", "value": "[Advance notice]"},
                     {"label": "Open to", "value": "[Hotel guests / visitors]"}, {"label": "Location", "value": "[Floor]"}],
     "Spa details strip", "wellness", None),
    ("lounge_work_note", "[Wi-Fi · airport transfer details]", "Business Lounge: Wi-Fi and transfer note", "lounge", None),
    ("getting_here", [{"label": "From Kempegowda International Airport", "value": "[Distance · drive time]"},
                      {"label": "From [railway station / metro]", "value": "[Distance · drive time]"},
                      {"label": "Parking", "value": "[Details]"}],
     "Getting here (Contact page)", "contact", None),
    ("map_embed_url", "", "Google Maps embed URL", "contact",
     "The src of the Google Maps embed iframe (https://www.google.com/maps/embed?...). Empty shows the placeholder."),
]


def _empty(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() == 0


def seed(db: Session) -> dict[str, int]:
    added: dict[str, int] = {}
    from app.services.role_service import ensure_built_in
    ensure_built_in(db)   # Administrator + Front desk access roles
    if _empty(db, RoomType):
        for r in ROOMS:
            db.add(RoomType(**ROOM_FACTS, max_adults=2, max_children=1, is_active=True, **{"is_signature": False, **r}))
        added["room_types"] = len(ROOMS)
    if _empty(db, SpaTreatment):
        for t in TREATMENTS:
            db.add(SpaTreatment(duration_label="[Duration]", price_label="From [PRICE]", **t))
        added["spa_treatments"] = len(TREATMENTS)
    if _empty(db, ContentCard):
        for i, (section, title, body, img, alt, meta) in enumerate(CARDS):
            db.add(ContentCard(section=section, title=title, body=body, image_url=IMG + img, image_alt=alt,
                               meta=meta, sort_order=i))
        added["content_cards"] = len(CARDS)
    if _empty(db, GalleryImage):
        for i, (img, alt, cat, layout, w, h, home) in enumerate(GALLERY):
            db.add(GalleryImage(image_url=IMG + img, alt=alt, category=cat, layout=layout, width=w, height=h,
                                on_home=home is not None, home_order=home or 0, sort_order=i))
        added["gallery_images"] = len(GALLERY)
    if _empty(db, JobOpening):
        for i in range(3):
            db.add(JobOpening(title="[Role title]", department="[Department]",
                              employment_type="[Full-time / Part-time]", sort_order=i))
        added["job_openings"] = 3
    existing = set(db.execute(select(SiteSetting.key)).scalars())
    n = 0
    for order, (key, value, label, group, help_text) in enumerate(SETTINGS):
        if key not in existing:
            db.add(SiteSetting(key=key, value=value, label=label, group=group, help_text=help_text, sort_order=order))
            n += 1
    if n:
        added["site_settings"] = n
    db.commit()
    return added
