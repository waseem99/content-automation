from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p23-step-03.md")


def test_p23_secrets_environment_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p23-step-01.md",
        "docs/operations/p23-step-02.md",
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p22-step-05.md",
        "docs/operations/p22-readiness-report.md",
        "Part of #313. Closes #316 after the PR merges.",
    ]:
        assert term in content


def test_p23_secrets_environment_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This secrets and environment exposure review is documentation-only.",
        "read secret values",
        "print secret values",
        "infer secret values",
        "rotate secrets",
        "create secrets",
        "delete secrets",
        "rename secrets",
        "change repository environments",
        "change deployment protection rules",
        "change GitHub Actions permissions",
        "expose private runtime values",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p23_secrets_environment_review_documents_secret_and_environment_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "secret names",
        "secret purpose summaries",
        "owner roles",
        "rotation decision status",
        "secret values",
        "partial secret values",
        "token fragments",
        "private environment dumps",
        "service account keys",
        "deploy key material",
        "webhook signing secrets",
        "environment name",
        "deployment purpose summary",
        "required reviewer status",
        "deployment branch restriction summary",
        "environment secret presence summary",
        "approval requirement summary",
        "private runtime value boundary",
        "Only summaries may be committed.",
    ]:
        assert term in content


def test_p23_secrets_environment_review_documents_rotation_and_evidence_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "no rotation needed",
        "rotation approved and scheduled outside repository evidence",
        "rotation required before production release",
        "rotation deferred with named owner, reason, and target review date",
        "blocked because value exposure is suspected and escalation is required",
        "issue or PR reference",
        "merge commit reference",
        "CI run identifier",
        "secret name summary",
        "environment name",
        "rotation decision status",
        "deployment protection summary",
        "required reviewer summary",
        "branch restriction summary",
        "secret value",
        "partial secret value",
        "token value",
        "token fragment",
        "service account key",
        "deploy key value",
        "webhook signing secret",
        "private runtime value",
        "private environment dump",
        "raw deployment log with restricted data",
        "customer data",
    ]:
        assert term in content


def test_p23_secrets_environment_review_documents_fields_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "review date",
        "secret or environment category",
        "safe purpose summary",
        "owner role",
        "reviewer role",
        "evidence location",
        "exposure status",
        "deployment protection status",
        "follow-up action",
        "follow-up owner role",
        "target review date",
        "closure criterion",
        "owner role is missing",
        "reviewer role is missing",
        "exposure status is missing",
        "rotation decision status is missing",
        "secret value is present",
        "partial secret value is present",
        "token value is present",
        "token fragment is present",
        "deploy key value is present",
        "service account key is present",
        "webhook signing secret is present",
        "private runtime value is present",
        "private environment dump is present",
        "customer data is present",
        "suspected exposure has no escalation route",
        "production launch is implied without explicit decision",
        "workflow gate bypass is requested",
        "No automatic secret reading.",
        "No automatic secret printing.",
        "No automatic secret inference.",
        "No automatic secret rotation.",
        "No automatic environment changes.",
        "No automatic deployment protection changes.",
        "No automatic GitHub Actions permission changes.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
