from pathlib import Path

from pydantic import ValidationError
import pytest

from src.operations.settings import OperationsSettings
from src.operator_api.entrypoint import _operator_auth_from_environment
from src.operator_api.runtime_config import OperatorRuntimeSettings


ROOT = Path(__file__).resolve().parents[2]
STAGING_ENV = ROOT / "config/staging.env.example"
PRODUCTION_ENV = ROOT / "config/production.env.example"


def test_staging_template_decodes_all_typed_operations_settings() -> None:
    settings = OperationsSettings(_env_file=STAGING_ENV)
    assert settings.environment == "staging"
    assert settings.rate_limit_exempt_paths == ("/health", "/runtime/ready")
    assert settings.allow_destructive_restore_drill is True
    assert settings.migrations_dir == Path("migrations")

    runtime = OperatorRuntimeSettings(_env_file=STAGING_ENV)
    assert runtime.auto_connect_database is True
    assert runtime.database_require_schema is True
    assert runtime.database_migrations_dir == Path("migrations")


def test_production_template_is_deliberately_non_runnable_until_identity_is_injected() -> None:
    with pytest.raises(ValidationError, match="non-placeholder release identity"):
        OperationsSettings(_env_file=PRODUCTION_ENV)

    runtime = OperatorRuntimeSettings(_env_file=PRODUCTION_ENV)
    assert runtime.auto_connect_database is True
    assert runtime.database_require_schema is True
    assert runtime.database_migrations_dir == Path("migrations")


def test_staging_auth_can_only_be_disabled_explicitly_outside_production(monkeypatch) -> None:
    monkeypatch.setenv("OPS_ENVIRONMENT", "staging")
    monkeypatch.setenv("OPERATOR_AUTH_ENABLED", "false")
    monkeypatch.delenv("OPERATOR_API_KEYS_JSON", raising=False)

    auth = _operator_auth_from_environment()
    assert auth.disabled is True
    assert auth.disabled_operator_id == "staging-local-operator"


def test_production_auth_requires_enabled_nonempty_external_key_map(monkeypatch) -> None:
    monkeypatch.setenv("OPS_ENVIRONMENT", "production")
    monkeypatch.setenv("OPERATOR_AUTH_ENABLED", "false")
    monkeypatch.delenv("OPERATOR_API_KEYS_JSON", raising=False)
    with pytest.raises(RuntimeError, match="cannot be false in production"):
        _operator_auth_from_environment()

    monkeypatch.setenv("OPERATOR_AUTH_ENABLED", "true")
    with pytest.raises(RuntimeError, match="required in production"):
        _operator_auth_from_environment()

    monkeypatch.setenv(
        "OPERATOR_API_KEYS_JSON",
        '{"external-key-reference":"admin.one"}',
    )
    auth = _operator_auth_from_environment()
    assert auth.disabled is False
    assert auth.resolve_identities_from_database is True
    assert auth.api_keys == {"external-key-reference": "admin.one"}
