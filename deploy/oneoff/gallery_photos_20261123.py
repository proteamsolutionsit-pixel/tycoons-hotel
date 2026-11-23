"""One-off (2026-11-23, staging): the hotel's own photos in the gallery.

Run from ~/tycoons with the app's virtualenv python. Idempotent: rows are matched by image_url, so a second
run changes nothing. Before writing, every gallery row is saved as JSON next to this script's output, so the
change can be reversed by hand.
"""
import json
import sys
from datetime import datetime

from app.db.session import SessionLocal
from app.models import GalleryImage
from app.models.enums import GalleryCategory as C, GalleryLayout as L

NEW = [  # image_url, alt, category, layout, width, height
    ("/assets/img/gal-gym.jpg", "Fitness centre", C.WELLNESS, L.WIDE, 1500, 1000),
    ("/assets/img/gal-corridor.jpg", "Guest floor corridor", C.SPACES, L.NORMAL, 900, 1200),
    ("/assets/img/gal-bar.jpg", "Bar counter at Fishy Tales", C.DINING, L.WIDE, 1500, 1000),
    ("/assets/img/gal-restaurant-seating.jpg", "Fishy Tales restaurant seating", C.DINING, L.NORMAL, 1500, 1000),
    ("/assets/img/gal-restaurant-mural.jpg", "Fishy Tales seaside mural", C.DINING, L.NORMAL, 900, 1200),
]
ALT = {  # existing rows whose picture was replaced by the hotel's photo: describe what is now shown
    "/assets/img/lobby-lounge.jpg": "Reception and lobby",
    "/assets/img/gal-restaurant.jpg": "Fishy Tales restaurant",
}

backup_path = sys.argv[1]
with SessionLocal() as db:
    rows = db.query(GalleryImage).order_by(GalleryImage.id).all()
    with open(backup_path, "w") as f:
        json.dump([{c.name: (getattr(r, c.name).value if hasattr(getattr(r, c.name), "value") else
                             getattr(r, c.name).isoformat() if isinstance(getattr(r, c.name), datetime) else getattr(r, c.name))
                    for c in GalleryImage.__table__.columns} for r in rows], f, indent=1)
    print("backed up", len(rows), "rows to", backup_path)
    by_url = {r.image_url: r for r in rows}
    top = max([r.sort_order for r in rows] or [0])
    for i, (url, alt, cat, lay, w, h) in enumerate(NEW, 1):
        if url in by_url:
            print("exists", url)
            continue
        db.add(GalleryImage(image_url=url, alt=alt, category=cat, layout=lay, width=w, height=h,
                            on_home=False, home_order=0, sort_order=top + i, is_active=True))
        print("added", url)
    for url, alt in ALT.items():
        r = by_url.get(url)
        if r and r.alt != alt:
            print("alt", url, repr(r.alt), "->", repr(alt))
            r.alt = alt
    db.commit()
    print("gallery rows now:", db.query(GalleryImage).count())
