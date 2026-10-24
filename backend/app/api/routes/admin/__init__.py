from fastapi import APIRouter

from app.api.routes.admin import auth, bookings, content, dashboard, payment_settings, submissions, users

router = APIRouter(prefix="/admin")
for module in (auth, dashboard, bookings, payment_settings, content, submissions, users):
    router.include_router(module.router)
