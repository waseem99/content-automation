from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from src.infrastructure.database.settings import (
    DatabaseConfigurationError,
    DatabaseSettings,
)


def test_database_url_is_required_only_when_used() -> None:
    settings = DatabaseSettings(_env_file=None, url=SecretStr(""))
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        settings.require_dsn()


def test_database_url_is_secret_and_validated() -> None:
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr("postgresql://user:password@localhost/db"),
    )
    assert "password" not in repr(settings)
    assert settings.require_dsn().startswith("postgresql")


def test_invalid_database_scheme_is_rejected() -> None:
    settings = DatabaseSettings(_env_file=None, url=SecretStr("sqlite:///tmp/test.db"))
    with pytest.raises(DatabaseConfigurationError, match="scheme"):
        settings.require_dsn()


def test_pool_minimum_cannot_exceed_maximum() -> None:
    with pytest.raises(ValidationError, match="POOL_MIN_SIZE"):
        DatabaseSettings(_env_file=None, pool_min_size=5, pool_max_size=2)
