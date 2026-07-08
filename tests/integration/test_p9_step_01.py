from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p9-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p9_deployment_dry_run_references_p8_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p8-step-01.md",
        "docs/operations/p8-step-02.md",
        ".env.production.example",
        "service image build expectations",
        "runtime command verification",
        "environment variable review",
    ]:
        assert term in content


def test_p9_deployment_dry_run_documents_preparation_and_execution() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "deployment operator",
        "database operator",
        "decision owner",
        "uvicorn src.operator_api.entrypoint:app --host 0.0.0.0 --port 8000",
        "DATABASE_REQUIRE_SCHEMA=true",
        "OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA=true",
        "Build or select the candidate runtime image.",
        "Keep external exposure private or internal.",
        "port `8000`",
    ]:
        assert term in content


def test_p9_deployment_dry_run_documents_runtime_checks() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "protected routes require operator access",
        "safe configuration route does not expose secrets",
        "workflow gates remain enforced",
    ]:
        assert term in content


def test_p9_deployment_dry_run_documents_stop_conditions_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Stop conditions",
        "migration readiness fails",
        "runtime config exposes a secret value",
        "protected route access is not enforced",
        "rollback owner is unavailable",
        "Evidence capture",
        "image tag or digest",
        "commit SHA",
        "stop condition result",
        "Do not record secret values.",
    ]:
        assert term in content


def test_p9_deployment_dry_run_preserves_guardrails_and_ci_wildcard() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")

    for term in [
        "No public production launch.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No secret values in logs.",
        "No private runtime values in evidence.",
    ]:
        assert term in content

    assert "tests/integration/test_p9_step_*.py" in harness
