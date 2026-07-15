from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.infrastructure.database.settings import DatabaseSettings


class OperatorRuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OPERATOR_RUNTIME_",
        extra="ignore",
    )

    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = Field(default="INFO")
    demo_mode: bool = Field(default=False)
    database_require_schema: bool = Field(default=True)
    database_migrations_dir: Path = Field(default=Path("migrations"))
    auto_connect_database: bool = Field(default=False)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError("OPERATOR_RUNTIME_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    def database_settings(self) -> DatabaseSettings:
        base = DatabaseSettings()
        return DatabaseSettings(
            url=base.url,
            pool_min_size=base.pool_min_size,
            pool_max_size=base.pool_max_size,
            pool_timeout_sec=base.pool_timeout_sec,
            connect_timeout_sec=base.connect_timeout_sec,
            statement_timeout_ms=base.statement_timeout_ms,
            application_name=base.application_name,
            migrations_dir=self.database_migrations_dir,
            require_schema=self.database_require_schema,
        )

    def public_snapshot(self) -> dict[str, Any]:
        return {
            "api_host": self.api_host,
            "api_port": self.api_port,
            "log_level": self.log_level,
            "demo_mode": self.demo_mode,
            "database_require_schema": self.database_require_schema,
            "database_migrations_dir": str(self.database_migrations_dir),
            "auto_connect_database": self.auto_connect_database,
        }


def get_operator_runtime_settings() -> OperatorRuntimeSettings:
    return OperatorRuntimeSettings()
