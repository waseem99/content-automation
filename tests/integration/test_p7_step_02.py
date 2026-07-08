from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import DatabaseSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app


pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
DOC = Path("docs/operations/p7-step-02.md")


@pytest.fixture()
def ready_database() -> Database:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=True,
        pool_min_size=1,
        pool_max_size=2,
    )
    db = Database(settings)
    db.open(require_schema=True)
    try:
        yield db
    finally:
        db.close()


def test_runtime_health_remains_public_liveness_check() -> None:
    settings = OperatorRuntimeSettings(database_require_schema=True, _env_file=None)
    client = TestClient(create_configured_app(runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "content-automation-operator-api"
    assert payload["database_configured"] is False
    assert payload["auth_required"] is False


def test_runtime_ready_fails_closed_without_database() -> None:
    settings = OperatorRuntimeSettings(database_require_schema=True, _env_file=None)
    client = TestClient(create_configured_app(runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    response = client.get("/runtime/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["kind"] == "runtime_readiness"
    assert payload["checks"] == {
        "runtime_configured": True,
        "database_configured": False,
        "database_reachable": False,
        "schema_required": True,
        "schema_ready": False,
        "migrations_ready": False,
    }
    assert payload["runtime"]["database_require_schema"] is True


def test_runtime_ready_succeeds_with_ready_database(ready_database: Database) -> None:
    settings = OperatorRuntimeSettings(database_require_schema=True, database_migrations_dir=ROOT / "migrations", _env_file=None)
    client = TestClient(create_configured_app(database=ready_database, runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    response = client.get("/runtime/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["kind"] == "runtime_readiness"
    assert payload["checks"]["runtime_configured"] is True
    assert payload["checks"]["database_configured"] is True
    assert payload["checks"]["database_reachable"] is True
    assert payload["checks"]["schema_required"] is True
    assert payload["checks"]["schema_ready"] is True
    assert payload["checks"]["migrations_ready"] is True


def test_runtime_config_remains_snapshot_route() -> None:
    settings = OperatorRuntimeSettings(api_host="0.0.0.0", api_port=8010, database_require_schema=False, _env_file=None)
    client = TestClient(create_configured_app(runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    response = client.get("/runtime/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["kind"] == "runtime_config"
    assert payload["runtime"]["api_host"] == "0.0.0.0"
    assert payload["runtime"]["api_port"] == 8010


def test_p7_readiness_notes_cover_checks_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "runtime_readiness",
        "database_configured",
        "database_reachable",
        "schema_required",
        "schema_ready",
        "migrations_ready",
        "HTTP 200",
        "HTTP 503",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No private runtime values are returned.",
    ]

    for term in required_terms:
        assert term in content
