from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p19-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p19_secret_hardening_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p18-readiness-report.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p19_secret_hardening_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This guide is documentation-only.",
        "create or rotate secrets",
        "expose secret values",
        "grant production access",
        "change production configuration",
        "approve production launch",
        "schedule production launch",
        "execute release activities",
        "bypass workflow gates",
        "publish configuration material",
        "export configuration evidence",
    ]:
        assert term in content


def test_p19_secret_hardening_documents_secret_configuration_and_environment_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "never commit secret values",
        "never store production tokens in docs",
        "never paste private runtime values into issues",
        "never include raw credentials in CI evidence",
        "never include private environment dumps in artifacts",
        "use named placeholders for configuration references",
        "route suspected exposure to security incident handling",
        "public configuration names",
        "non-secret environment variable names",
        "secret environment variable names",
        "production-only values",
        "development-only values",
        "CI-only values",
        "restricted runtime values",
        "Do not record live production values.",
        "variable name placeholder",
        "purpose summary",
        "owner role",
        "required or optional status",
        "rotation expectation",
        "environment scope",
        "validation route",
        "Environment variable documentation must not include actual secret values.",
    ]:
        assert term in content


def test_p19_secret_hardening_documents_forbidden_values_redaction_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "passwords",
        "API keys",
        "OAuth tokens",
        "session tokens",
        "private signing keys",
        "database credentials",
        "production connection strings",
        "cloud provider credentials",
        "webhook secrets",
        "raw environment dumps",
        "remove exact restricted values",
        "replace values with named placeholders",
        "preserve enough context for review",
        "record redaction owner",
        "record redaction reason",
        "record evidence sensitivity after redaction",
        "block closeout if redaction cannot be confirmed",
        "hardening item identifier",
        "configuration area",
        "secret exposure status",
        "configuration review status",
        "redaction status",
        "validation requirement",
        "closure criteria",
        "not started",
        "ready for review",
        "reviewed",
        "reviewed with notes",
        "exposure suspected",
        "exposure confirmed",
        "blocked by guardrail",
    ]:
        assert term in content


def test_p19_secret_hardening_documents_validation_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no docs require live secret values",
        "no tests require live secret values",
        "P19 integration tests are included in CI",
        "forbidden value classes are documented",
        "evidence exclusions are documented",
        "redaction rules are documented",
        "stop conditions are documented",
        "guardrails are preserved",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized configuration notes",
        "summarized redaction notes",
        "summarized hardening notes",
        "summarized reviewer notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered configuration materials",
        "scheduled configuration outputs",
        "owner is missing",
        "reviewer is missing",
        "evidence source is missing",
        "evidence sensitivity is missing",
        "configuration review status is missing",
        "redaction status is missing",
        "suspected exposure has no action owner",
        "confirmed exposure has no security incident route",
        "actual secret value is present",
        "private runtime value is present",
        "raw credential is present",
        "production token is present",
        "customer data export is requested",
        "external package export is requested",
        "production configuration change is implied",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content


def test_p19_secret_hardening_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p19_step_*.py" in harness
