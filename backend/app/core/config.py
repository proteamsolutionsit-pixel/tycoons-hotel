"""Application settings, read from environment variables (and backend/.env).

Keep .env values on their own lines: `KEY=value`, with comments on separate
lines. systemd's EnvironmentFile does not strip trailing `# comments`."""
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
    # staging = a public pre-production site: every production safeguard applies,
    # but test payments (PAYMENT_MODE=mock) are allowed. production allows real payments only.
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Database ---------------------------------------------------------------
    # Runtime account: DML only (see scripts/mysql-grant-app-user.ps1).
    database_url: str = "mysql+pymysql://tycoons_app:change-me@127.0.0.1:3308/tycoons?charset=utf8mb4"  # pragma: allowlist secret
    # Schema owner used by Alembic only. Falls back to DATABASE_URL.
    migration_database_url: str = ""
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 10
    database_pool_timeout: int = 10        # seconds to wait for a free connection
    database_connect_timeout: int = 10
    database_read_timeout: int = 30        # per query, seconds
    database_ssl_ca: str = ""              # path to CA bundle -> TLS to MySQL

    # HTTP -------------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"
    # Host headers accepted (comma-separated). "*" disables the check (dev only).
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    public_base_url: str = "http://localhost:5173"   # used in emailed links
    max_json_body_bytes: int = 1 * 1024 * 1024
    max_upload_body_bytes: int = 9 * 1024 * 1024
    frontend_dist: Path | None = None

    # Staff sessions -----------------------------------------------------------
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict"] = "lax"
    password_reset_minutes: int = 30

    # Razorpay ---------------------------------------------------------------
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_timeout_seconds: int = 15
    currency: str = "INR"
    # "mock" = test payments without a Razorpay account (development only;
    # production refuses to start with it).
    payment_mode: Literal["razorpay", "mock"] = "razorpay"

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
    # "database": shared by all workers/hosts (production). "memory": per process.
    rate_limit_backend: Literal["database", "memory"] = "database"

    @field_validator("storage_dir", mode="after")
    @classmethod
    def _absolute_storage(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment not in ("staging", "production"):
            return self
        problems = []
        if self.environment == "production" and self.payment_mode != "razorpay":
            problems.append("PAYMENT_MODE must be razorpay (test payments are not allowed in production)")
        if self.payment_mode == "razorpay" and not (
                self.razorpay_key_id and self.razorpay_key_secret and self.razorpay_webhook_secret):
            problems.append("RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET are required")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (serve over HTTPS)")
        if "*" in self.allowed_host_list:
            problems.append("ALLOWED_HOSTS must list the real host names")
        if "*" in self.cors_origin_list:
            problems.append("CORS_ORIGINS must not be *")
        if not self.public_base_url.startswith("https://"):
            problems.append("PUBLIC_BASE_URL must be https://")
        if self.rate_limit_backend != "database":
            problems.append("RATE_LIMIT_BACKEND must be database")
        if problems:
            raise ValueError(f"Unsafe {self.environment} configuration: " + "; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def migration_url(self) -> str:
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
