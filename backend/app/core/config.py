from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value can be set through a LODGEOS_* environment variable."""

    model_config = SettingsConfigDict(env_prefix="LODGEOS_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"

    # The API connects as lodgeos_app, which is subject to Row-Level Security.
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://lodgeos_app:app-dev-only@127.0.0.1:5432/lodgeos"
    )
    # Migrations and operator commands connect as lodgeos_owner.
    migration_database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://lodgeos_owner:owner-dev-only@127.0.0.1:5432/lodgeos"
    )
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")

    # Sessions
    session_cookie_name: str = "lodgeos_session"
    csrf_cookie_name: str = "lodgeos_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_idle_timeout_minutes: int = Field(default=12 * 60, ge=5)
    session_absolute_timeout_hours: int = Field(default=7 * 24, ge=1)

    # Login throttling (per email and per client IP, fixed window)
    login_max_attempts: int = Field(default=10, ge=1)
    login_window_seconds: int = Field(default=15 * 60, ge=60)

    # Comma-separated list of origins allowed to call the API with credentials.
    cors_allowed_origins: str = "http://localhost:3000"

    # Where guests open links from emails (booking pages, guest portal).
    public_base_url: str = "http://localhost:3000"

    # Email (ADR-0011). "mock" records messages without sending; production needs "smtp".
    email_provider: Literal["mock", "smtp"] = "mock"
    email_from_address: str = "bookings@lodgeos.local"
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    # "starttls" upgrades a plain connection (port 587); "tls" connects over TLS (port 465).
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_timeout_seconds: float = Field(default=20, gt=0, le=120)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
