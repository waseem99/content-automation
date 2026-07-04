"""Database-specific configuration.

The database settings are intentionally separate from the legacy media pipeline
settings so existing extraction commands do not require PostgreSQL until they
opt into the platform foundation.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfigurationError(RuntimeError):
    """Raised when required database configuration is missing or inconsistent."""


class DatabaseSettings(BaseSettings):
    """Validated PostgreSQL and pool settings.

    Environment variables use the ``DATABASE_`` prefix, for example
    ``DATABASE_URL`` and ``DATABASE_POOL_MAX_SIZE``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DATABASE_",
        extra="ignore",
    )

    url: SecretStr = Field(default=SecretStr(""))
    pool_min_size: int = Field(default=1, ge=1, le=50)
    pool_max_size: int = Field(default=10, ge=1, le=100)
    pool_timeout_sec: float = Field(default=15.0, gt=0, le=120)
    connect_timeout_sec: int = Field(default=10, ge=1, le=120)
    statement_timeout_ms: int = Field(default=60_000, ge=1_000, le=3_600_000)
    application_name: str = Field(default="football-brief")
    migrations_dir: Path = Field(default=Path("migrations"))
    require_schema: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_pool_bounds(self) -> "DatabaseSettings":
        if self.pool_min_size > self.pool_max_size:
            raise ValueError("DATABASE_POOL_MIN_SIZE cannot exceed DATABASE_POOL_MAX_SIZE")
        return self

    def require_dsn(self) -> str:
        dsn = self.url.get_secret_value().strip()
        if not dsn:
            raise DatabaseConfigurationError(
                "DATABASE_URL is required for database commands and platform services"
            )
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise DatabaseConfigurationError(
                "DATABASE_URL must use a postgresql:// or postgres:// scheme"
            )
        return dsn


def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()
