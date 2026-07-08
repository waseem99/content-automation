from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p23-step-02.md")


def test_p23_branch_protection_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p23-step-01.md",
        "docs/operations/p22-readiness-report.md",
        "docs/operations/p22-closeout-checklist.md",
        ".github/workflows/p1-acceptance-harness.yml",
        "Part of #313. Closes #315 after the PR merges.",
    ]:
        assert term in content


def test_p23_branch_protection_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This branch protection and required-check review is documentation-only.",
        "change branch protection settings",
        "add required checks",
        "remove required checks",
        "enable auto-merge",
        "disable auto-merge",
        "merge a pull request",
        "approve a pull request",
        "bypass workflow gates",
        "expose secret values",
        "expose private runtime values",
        "approve production launch",
        "schedule production launch",
    ]:
        assert term in content


def test_p23_branch_protection_review_documents_required_checks_and_exact_head_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact current PR head SHA",
        "identify the current PR head SHA immediately before evaluating CI",
        "fetch workflow runs for that same SHA",
        "confirm each required workflow run is completed",
        "confirm each required workflow run conclusion is success",
        "do not reuse CI evidence from an older commit",
        "do not merge after a new commit is pushed until fresh CI passes on the new head",
        "use an expected head SHA gate when merging",
    ]:
        assert term in content


def test_p23_branch_protection_review_documents_branch_rules_and_evidence_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "required status checks are enabled",
        "required check names match the implementation workflow gate names",
        "stale approvals are not relied on after new commits",
        "direct pushes to protected branches are restricted where appropriate",
        "force pushes are restricted where appropriate",
        "deletions are restricted where appropriate",
        "auto-merge remains disabled unless explicitly approved",
        "branch rules are reviewed before production release",
        "exceptions require a named owner, reason, expiry, and follow-up date",
        "issue or PR reference",
        "merge commit reference",
        "CI run identifier",
        "branch name",
        "required check name",
        "required check result summary",
        "exact head SHA",
        "branch rule summary",
        "exception summary",
        "private collaborator list",
        "private team membership list",
        "private email address list",
        "private audit log export",
        "secret value",
        "token value",
        "deploy key value",
        "private runtime value",
        "customer data",
    ]:
        assert term in content


def test_p23_branch_protection_review_documents_fields_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "review date",
        "branch reviewed",
        "required checks reviewed",
        "exact-head CI rule reviewed",
        "direct push restriction status",
        "force push restriction status",
        "deletion restriction status",
        "auto-merge status",
        "owner role",
        "reviewer role",
        "decision status",
        "exception status",
        "follow-up owner role",
        "target review date",
        "closure criterion",
        "required check names are missing",
        "exact-head CI rule is missing",
        "CI evidence belongs to an older head SHA",
        "one required check is missing",
        "one required check is not successful",
        "auto-merge is used without explicit approval",
        "direct push bypass is requested",
        "workflow gate bypass is requested",
        "secret value is present",
        "private runtime value is present",
        "production launch is implied without explicit decision",
        "No automatic branch protection changes.",
        "No automatic required-check changes.",
        "No automatic direct-push exception.",
        "No automatic force-push exception.",
        "No auto-merge.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
