from fastapi import APIRouter

from app.api.routes.admin import auth, bookings, content, dashboard, submissions, users

router = APIRouter(prefix="/admin")
for module in (auth, dashboard, bookings, content, submissions, users):
    router.include_router(module.router)
