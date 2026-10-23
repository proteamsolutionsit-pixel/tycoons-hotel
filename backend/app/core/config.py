"""Application settings, read from environment variables (and backend/.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "The Tycoons Hotel API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Database ---------------------------------------------------------------
    database_url: str = "mysql+pymysql://tycoons:change-me@127.0.0.1:3308/tycoons?charset=utf8mb4"
    database_echo: bool = False

    # HTTP -------------------------------------------------------------------
    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173"
    # Serve the built React app (frontend/dist) from FastAPI. Optional; nginx
    # can do this instead in production.
    frontend_dist: Path | None = None

    # Admin auth -------------------------------------------------------------
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict"] = "lax"

    # Razorpay ---------------------------------------------------------------
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_timeout_seconds: int = 15
    currency: str = "INR"

    # Hotel rules ------------------------------------------------------------
    hotel_name: str = "The Tycoons Hotel"
    hotel_timezone: str = "Asia/Kolkata"
    booking_hold_minutes: int = 15
    max_stay_nights: int = 30
    max_advance_days: int = 365

    # Files ------------------------------------------------------------------
    storage_dir: Path = BACKEND_DIR / "storage"
    media_url_prefix: str = "/media"
    max_cv_bytes: int = 5 * 1024 * 1024
    max_image_bytes: int = 8 * 1024 * 1024

    # Mail (optional; without SMTP_HOST messages are only logged) -------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    mail_from: str = "The Tycoons Hotel <no-reply@example.com>"
    hotel_notify_email: str = ""

    # Rate limiting ----------------------------------------------------------
    rate_limit_enabled: bool = True

    @field_validator("storage_dir", mode="after")
    @classmethod
    def _absolute_storage(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.environment == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if not (self.razorpay_key_id and self.razorpay_key_secret and self.razorpay_webhook_secret):
                raise ValueError("Razorpay keys and webhook secret are required in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production (serve over HTTPS)")
        elif not self.jwt_secret:
            # Development convenience only; production refuses to start without one.
            self.jwt_secret = "dev-only-insecure-secret-change-me-0123456789"
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
