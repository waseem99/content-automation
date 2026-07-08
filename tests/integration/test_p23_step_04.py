from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p23-step-04.md")


def test_p23_dependency_package_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p23-step-01.md",
        "docs/operations/p23-step-02.md",
        "docs/operations/p23-step-03.md",
        "docs/operations/p22-step-05.md",
        "docs/operations/p22-readiness-report.md",
        "requirements.txt",
        "Part of #313. Closes #317 after the PR merges.",
    ]:
        assert term in content


def test_p23_dependency_package_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This dependency and package access review is documentation-only.",
        "install new dependencies",
        "upgrade dependencies",
        "remove dependencies",
        "publish packages",
        "export private packages",
        "create package registry credentials",
        "rotate package registry credentials",
        "expose package registry credentials",
        "add package maintainers",
        "remove package maintainers",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p23_dependency_package_review_documents_dependency_and_access_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "dependency source file",
        "runtime dependency category",
        "development dependency category",
        "package registry source",
        "pinned or ranged version summary",
        "license review status",
        "security review status",
        "public package names",
        "private package credentials",
        "package registry tokens",
        "private index URLs with credentials",
        "private package artifacts",
        "package registry name",
        "package namespace or scope summary",
        "package owner role",
        "package maintainer role",
        "publish permission summary",
        "read permission summary",
        "automation identity summary",
        "token storage location summary",
        "external distribution status",
        "package export decision status",
        "Only role-level and status-level summaries may be committed.",
    ]:
        assert term in content


def test_p23_dependency_package_review_documents_distribution_and_evidence_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "no package publishing approved",
        "publishing blocked until explicit production decision",
        "private package distribution approved outside repository evidence",
        "external package export rejected",
        "external package export deferred with owner, reason, and target review date",
        "blocked because registry credential exposure is suspected and escalation is required",
        "issue or PR reference",
        "merge commit reference",
        "CI run identifier",
        "dependency source file name",
        "public dependency name",
        "package namespace summary",
        "publish permission summary",
        "package registry credential",
        "package registry token",
        "private index URL with credential",
        "private package artifact",
        "private maintainer list",
        "private account list",
        "service account key",
        "token value",
        "secret value",
        "private runtime value",
        "external package export",
        "raw registry audit export",
    ]:
        assert term in content


def test_p23_dependency_package_review_documents_fields_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "review date",
        "dependency source reviewed",
        "package registry reviewed",
        "package namespace or scope summary",
        "owner role",
        "reviewer role",
        "evidence location",
        "license review status",
        "security review status",
        "publish permission summary",
        "package export decision status",
        "follow-up action",
        "follow-up owner role",
        "target review date",
        "closure criterion",
        "dependency source reviewed is missing",
        "package registry reviewed is missing",
        "owner role is missing",
        "reviewer role is missing",
        "license review status is missing",
        "security review status is missing",
        "package export decision status is missing",
        "package registry credential is present",
        "package registry token is present",
        "private index URL with credential is present",
        "private package artifact is present",
        "private maintainer list is present",
        "external package export is requested without explicit approval",
        "registry credential exposure is suspected and no escalation route exists",
        "production launch is implied without explicit decision",
        "workflow gate bypass is requested",
        "No automatic dependency install.",
        "No automatic dependency upgrade.",
        "No automatic dependency removal.",
        "No automatic package publishing.",
        "No automatic package export.",
        "No automatic registry credential changes.",
        "No automatic package maintainer changes.",
        "No workflow gate bypass.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
