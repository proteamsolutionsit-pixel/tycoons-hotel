from fastapi import APIRouter

from app.api.routes import admin, bookings, forms, payments, public

api_router = APIRouter(prefix="/api")
api_router.include_router(public.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)
api_router.include_router(forms.router)
api_router.include_router(admin.router)
