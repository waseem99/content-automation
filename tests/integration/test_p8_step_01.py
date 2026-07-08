from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p8-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p8_service_definition_records_identity_and_runtime_command() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "content-automation-operator-api",
        "Dockerfile",
        ".dockerignore",
        "docker build -t content-automation-operator:local .",
        "uvicorn src.operator_api.entrypoint:app --host 0.0.0.0 --port 8000",
        "src.operator_api.entrypoint:app",
        "src.operator_api.entrypoint:create_runtime_app",
        "8000",
    ]:
        assert term in content


def test_p8_service_definition_records_process_model_and_dependencies() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "one web process per container",
        "horizontal scale by adding runtime instances",
        "no in-process scheduler",
        "no background publishing worker",
        "PostgreSQL database reachable through `DATABASE_URL`",
        "applied migrations in `migrations`",
        "operator access configuration",
        "runtime environment variables supplied outside the image",
    ]:
        assert term in content


def test_p8_service_definition_records_runtime_checks_and_restart_policy() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "Readiness must pass before internal operator workflow actions begin.",
        "restart failed runtime process",
        "readiness failure should remove the instance from serving traffic",
        "liveness failure should restart the instance",
    ]:
        assert term in content


def test_p8_service_definition_records_boundaries_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "AWS ECS",
        "Kubernetes",
        "VM systemd",
        "serverless platform",
        "managed container platform",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
        "No private runtime values.",
    ]:
        assert term in content


def test_p8_acceptance_harness_includes_step_wildcard() -> None:
    content = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p8_step_*.py" in content
