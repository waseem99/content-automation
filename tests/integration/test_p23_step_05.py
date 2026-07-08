from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p23-step-05.md")


def test_p23_evidence_boundary_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p23-step-01.md",
        "docs/operations/p23-step-02.md",
        "docs/operations/p23-step-03.md",
        "docs/operations/p23-step-04.md",
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p22-step-05.md",
        "docs/operations/p22-readiness-report.md",
        "Part of #313. Closes #318 after the PR merges.",
    ]:
        assert term in content


def test_p23_evidence_boundary_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This public/private evidence boundary review is documentation-only.",
        "collect production evidence",
        "export production evidence",
        "publish evidence externally",
        "commit private access lists",
        "commit customer data",
        "commit secret values",
        "commit private runtime values",
        "commit private package artifacts",
        "change repository visibility",
        "change collaborator access",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p23_evidence_boundary_review_documents_public_and_private_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "issue reference",
        "PR reference",
        "merge commit reference",
        "CI run identifier",
        "workflow name",
        "branch name",
        "current head SHA",
        "documentation path",
        "test path",
        "public configuration file name",
        "non-sensitive decision status",
        "role-level owner summary",
        "role-level reviewer summary",
        "redacted risk summary",
        "closeout checklist status",
        "customer data",
        "secret value",
        "partial secret value",
        "token value",
        "token fragment",
        "service account key",
        "deploy key value",
        "webhook signing secret",
        "private runtime value",
        "private environment dump",
        "raw production log",
        "raw deployment log",
        "raw audit log export",
        "private collaborator list",
        "private team membership list",
        "private package artifact",
        "private registry credential",
        "screenshot containing restricted data",
        "external package export",
    ]:
        assert term in content


def test_p23_evidence_boundary_review_documents_redaction_minimization_and_categories() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "raw evidence is not required when a summary is enough",
        "values are replaced with role-level or status-level summaries",
        "private user names are omitted unless already public and necessary",
        "private email addresses are omitted",
        "secret names are included only when safe and necessary",
        "secret values and fragments are removed",
        "customer identifiers are removed",
        "screenshots are avoided when text summaries are enough",
        "any screenshot is reviewed for restricted values before use",
        "logs are summarized instead of copied",
        "package artifacts are not committed",
        "external exports are not attached",
        "safe to commit as-is",
        "safe to commit after redaction",
        "safe to summarize only",
        "private off-repository evidence",
        "blocked by restricted data",
        "blocked by missing owner review",
        "blocked by workflow gate",
    ]:
        assert term in content


def test_p23_evidence_boundary_review_documents_fields_stops_checklist_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "review date",
        "evidence item identifier",
        "evidence category",
        "source location",
        "proposed repository location",
        "sensitivity level",
        "redaction status",
        "minimization status",
        "owner role",
        "reviewer role",
        "decision status",
        "follow-up action",
        "follow-up owner role",
        "target review date",
        "closure criterion",
        "evidence item identifier is missing",
        "evidence category is missing",
        "sensitivity level is missing",
        "redaction status is missing",
        "minimization status is missing",
        "customer data is present",
        "secret value is present",
        "partial secret value is present",
        "token value is present",
        "token fragment is present",
        "private runtime value is present",
        "private environment dump is present",
        "private access list is present",
        "private package artifact is present",
        "private registry credential is present",
        "external package export is requested",
        "production evidence export is requested without explicit approval",
        "production launch is implied without explicit decision",
        "workflow gate bypass is requested",
        "committed evidence uses public operational references where possible",
        "private evidence remains off-repository",
        "CI evidence references exact-head run identifiers only",
        "No automatic evidence collection.",
        "No automatic evidence export.",
        "No automatic repository visibility changes.",
        "No automatic access changes.",
        "No automatic secret reading.",
        "No automatic package publishing.",
        "No automatic package export.",
        "No workflow gate bypass.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
