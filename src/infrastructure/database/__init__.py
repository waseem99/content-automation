"""PostgreSQL persistence foundation for Football Brief."""

from src.infrastructure.database.connection import (
    Database,
    DatabaseHealth,
    DatabaseSchemaError,
    DatabaseUnavailableError,
)
from src.infrastructure.database.settings import (
    DatabaseConfigurationError,
    DatabaseSettings,
    get_database_settings,
)

__all__ = [
    "Database",
    "DatabaseHealth",
    "DatabaseSchemaError",
    "DatabaseUnavailableError",
    "DatabaseConfigurationError",
    "DatabaseSettings",
    "get_database_settings",
]
