from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p11-step-04.md")


def test_p11_evidence_archive_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-step-01.md",
        "docs/operations/p11-step-03.md",
        "docs/operations/p10-readiness-report.md",
        "docs/operations/p10-closeout-checklist.md",
    ]:
        assert term in content


def test_p11_evidence_archive_documents_structure_index_and_retention() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "rollout reviews",
        "alert tuning reviews",
        "incident reviews",
        "deployment decisions",
        "smoke test evidence",
        "entry ID",
        "related issue or PR",
        "redaction status",
        "retention class",
        "stabilization record",
        "incident record",
        "temporary working note",
    ]:
        assert term in content


def test_p11_evidence_archive_documents_access_redaction_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence archive owner manages structure",
        "decision owner approves access changes",
        "public sharing is not allowed",
        "raw secret values are not allowed",
        "remove tokens",
        "remove connection strings",
        "remove raw operator keys",
        "weekly during stabilization",
        "before P11 closeout",
    ]:
        assert term in content


def test_p11_evidence_archive_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence includes secret values",
        "owner is unknown",
        "retention class is missing",
        "entry lacks related issue or PR",
        "disposal would remove active incident evidence",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No public sharing of production evidence.",
        "No evidence disposal without review.",
        "No automatic approval.",
        "No workflow gate bypass.",
    ]:
        assert term in content
