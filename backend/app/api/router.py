from fastapi import APIRouter

from app.api.routes import admin, bookings, forms, payments, public


def build_api_router(prefix: str, *, include_in_schema: bool = True) -> APIRouter:
    router = APIRouter(prefix=prefix, include_in_schema=include_in_schema)
    router.include_router(public.router)
    router.include_router(bookings.router)
    router.include_router(payments.router)
    router.include_router(forms.router)
    router.include_router(admin.router)
    return router


API_PREFIX = "/api/v1"
api_router = build_api_router(API_PREFIX)
# Pre-versioning paths keep working (existing links and the Razorpay webhook
# URL configured as /api/payments/webhook). Hidden from the docs and marked
# deprecated in responses; remove once nothing calls them.
legacy_api_router = build_api_router("/api", include_in_schema=False)
