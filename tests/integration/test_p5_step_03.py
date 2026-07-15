from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app


pytestmark = pytest.mark.integration


def test_runtime_settings_defaults_are_safe() -> None:
    settings = OperatorRuntimeSettings(_env_file=None)

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"
    assert settings.demo_mode is False
    assert settings.database_require_schema is True
    assert settings.database_migrations_dir == Path("migrations")
    assert settings.auto_connect_database is False
    assert settings.public_snapshot() == {
        "api_host": "127.0.0.1",
        "api_port": 8000,
        "log_level": "INFO",
        "demo_mode": False,
        "database_require_schema": True,
        "database_migrations_dir": "migrations",
        "auto_connect_database": False,
    }


def test_runtime_settings_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OPERATOR_RUNTIME_API_HOST", "0.0.0.0")
    monkeypatch.setenv("OPERATOR_RUNTIME_API_PORT", "8010")
    monkeypatch.setenv("OPERATOR_RUNTIME_LOG_LEVEL", "debug")
    monkeypatch.setenv("OPERATOR_RUNTIME_DEMO_MODE", "true")
    monkeypatch.setenv("OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA", "false")
    monkeypatch.setenv("OPERATOR_RUNTIME_DATABASE_MIGRATIONS_DIR", "custom_migrations")

    settings = OperatorRuntimeSettings(_env_file=None)

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8010
    assert settings.log_level == "DEBUG"
    assert settings.demo_mode is True
    assert settings.database_require_schema is False
    assert settings.database_migrations_dir == Path("custom_migrations")
    db_settings = settings.database_settings()
    assert db_settings.require_schema is False
    assert db_settings.migrations_dir == Path("custom_migrations")


def test_configured_app_exposes_runtime_snapshot() -> None:
    settings = OperatorRuntimeSettings(api_host="0.0.0.0", api_port=8010, log_level="warning", demo_mode=True, database_require_schema=False, _env_file=None)
    client = TestClient(create_configured_app(runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    health = client.get("/health").json()
    runtime = client.get("/runtime/config").json()

    assert health["ok"] is True
    assert runtime["ok"] is True
    assert runtime["kind"] == "runtime_config"
    assert runtime["runtime"] == {
        "api_host": "0.0.0.0",
        "api_port": 8010,
        "log_level": "WARNING",
        "demo_mode": True,
        "database_require_schema": False,
        "database_migrations_dir": "migrations",
    }
