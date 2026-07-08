from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p23-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p23_repository_visibility_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p22-readiness-report.md",
        "docs/operations/p22-closeout-checklist.md",
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p22-step-04.md",
        "docs/operations/p22-step-05.md",
        "Part of #313. Closes #314 after the PR merges.",
    ]:
        assert term in content


def test_p23_repository_visibility_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This repository visibility and access review is documentation-only.",
        "change repository visibility",
        "add repository collaborators",
        "remove repository collaborators",
        "modify repository roles",
        "grant admin access",
        "revoke admin access",
        "expose private access lists",
        "expose secret values",
        "expose private runtime values",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p23_repository_visibility_review_documents_observation_and_manual_decision() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "repository: waseem99/content-automation",
        "default branch: test",
        "visibility: public",
        "auto-merge: disabled",
        "production hardening risk boundary",
        "return the repository to private",
        "keep the repository public with an explicit accepted-risk note",
        "defer the visibility change with a named owner, reason, and target review date",
        "when CI no longer requires public visibility",
    ]:
        assert term in content


def test_p23_repository_visibility_review_documents_access_scope_and_evidence_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "repository owner",
        "administrator users",
        "maintain users",
        "write users",
        "triage users",
        "read-only users",
        "deploy key holders",
        "automation identities",
        "GitHub Actions permissions",
        "external integrations with repository access",
        "Only role names and summarized counts may be included in repository evidence.",
        "issue or PR reference",
        "merge commit reference",
        "CI run identifier",
        "current visibility summary",
        "default branch name",
        "auto-merge setting summary",
        "manual decision status",
        "private collaborator list",
        "private team membership list",
        "private email address list",
        "invitation URL",
        "deploy key value",
        "token value",
        "secret value",
        "private runtime value",
        "raw audit log export",
        "screenshot containing restricted data",
    ]:
        assert term in content


def test_p23_repository_visibility_review_documents_fields_stops_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "review date",
        "repository reviewed",
        "visibility state",
        "owner role",
        "reviewer role",
        "access category reviewed",
        "evidence location",
        "decision status",
        "follow-up action",
        "follow-up owner role",
        "target review date",
        "closure criterion",
        "repository visibility is public and no manual decision is recorded",
        "owner role is missing",
        "reviewer role is missing",
        "decision status is missing",
        "private collaborator list is included in repository evidence",
        "secret value is present",
        "private runtime value is present",
        "customer data is present",
        "deploy key value is present",
        "token value is present",
        "production launch is implied without explicit decision",
        "workflow gate bypass is requested",
        "No automatic visibility changes.",
        "No automatic access changes.",
        "No automatic collaborator changes.",
        "No automatic deploy key changes.",
        "No automatic secret rotation.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content

    assert "tests/integration/test_p23_step_*.py" in harness
