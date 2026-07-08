from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p8-step-02.md")
PROD_EXAMPLE = Path(".env.production.example")


def test_p8_environment_notes_record_required_variables() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "DATABASE_URL",
        "DATABASE_POOL_MIN_SIZE",
        "DATABASE_POOL_MAX_SIZE",
        "DATABASE_REQUIRE_SCHEMA",
        "OPERATOR_RUNTIME_API_HOST",
        "OPERATOR_RUNTIME_API_PORT",
        "OPERATOR_RUNTIME_LOG_LEVEL",
        "OPERATOR_RUNTIME_DEMO_MODE",
        "OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA",
        "OPERATOR_RUNTIME_DATABASE_MIGRATIONS_DIR",
        "OPENAI_MODEL",
        "ELEVENLABS_MODEL",
        "WHISPER_MODEL",
        "OPENAI_IMAGE_MODEL",
    ]:
        assert term in content


def test_p8_environment_notes_separate_secrets_from_safe_config() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Required secrets",
        "deployment environment or secret manager",
        "OPENAI_API_KEY",
        "SERPAPI_API_KEY",
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "operator access value for protected routes",
        "Checked-in files must not contain real secret values.",
    ]:
        assert term in content


def test_p8_production_example_contains_safe_defaults_only() -> None:
    content = PROD_EXAMPLE.read_text(encoding="utf-8")

    for term in [
        "DATABASE_URL=",
        "DATABASE_APPLICATION_NAME=content-automation-operator-production",
        "DATABASE_REQUIRE_SCHEMA=true",
        "OPERATOR_RUNTIME_API_HOST=0.0.0.0",
        "OPERATOR_RUNTIME_API_PORT=8000",
        "OPERATOR_RUNTIME_LOG_LEVEL=INFO",
        "OPERATOR_RUNTIME_DEMO_MODE=false",
        "OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA=true",
        "OPENAI_MODEL=gpt-4o-mini",
        "ELEVENLABS_MODEL=eleven_multilingual_v2",
        "OPENAI_IMAGE_MODEL=gpt-image-1.5",
    ]:
        assert term in content

    for forbidden in [
        "sk-",
        "password=",
        "PASSWORD=",
        "token=",
        "TOKEN=",
    ]:
        assert forbidden not in content


def test_p8_environment_notes_record_predeploy_checks_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "protected routes require operator access",
        "No secret values in git.",
        "No shared staging and production secrets.",
        "No private runtime values in public snapshots.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
    ]:
        assert term in content
