from pathlib import Path

from pydantic import ValidationError
import pytest

from src.operations.settings import OperationsSettings


ROOT = Path(__file__).resolve().parents[2]
STAGING_ENV = ROOT / "config/staging.env.example"
PRODUCTION_ENV = ROOT / "config/production.env.example"


def test_staging_template_decodes_all_typed_operations_settings() -> None:
    settings = OperationsSettings(_env_file=STAGING_ENV)
    assert settings.environment == "staging"
    assert settings.rate_limit_exempt_paths == ("/health", "/runtime/ready")
    assert settings.allow_destructive_restore_drill is True
    assert settings.migrations_dir == Path("migrations")


def test_production_template_is_deliberately_non_runnable_until_identity_is_injected() -> None:
    with pytest.raises(ValidationError, match="non-placeholder release identity"):
        OperationsSettings(_env_file=PRODUCTION_ENV)
