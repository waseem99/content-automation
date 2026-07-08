from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p13-step-02.md")


def test_p13_backup_restore_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p13-step-01.md",
        "docs/operations/p12-step-04.md",
        "docs/operations/p12-readiness-report.md",
    ]:
        assert term in content


def test_p13_backup_restore_documents_inventory_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "production database",
        "migration state",
        "configuration records",
        "evidence archive records",
        "monitoring configuration",
        "alert routing configuration",
        "backup ID",
        "protected surface",
        "backup owner",
        "backup cadence",
        "retention class",
        "restore validation owner",
    ]:
        assert term in content


def test_p13_backup_restore_documents_restore_evidence_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "restore test date",
        "source backup ID",
        "restore target",
        "validation method",
        "data integrity check",
        "owner signoff",
        "backup inventory review monthly",
        "restore validation at least quarterly",
        "retention review quarterly",
        "closeout evidence review before P13 closeout",
    ]:
        assert term in content


def test_p13_backup_restore_documents_retention_decisions_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "disposal must not remove active incident evidence",
        "disposal must have evidence archive owner approval",
        "backup evidence accepted",
        "restore validation required",
        "backup owner is missing",
        "restore validation owner is missing",
        "validation failed without corrective action",
        "No backup review closure without evidence.",
        "No restore review closure without validation evidence.",
        "No ownerless backup entry.",
        "No evidence disposal without approval.",
        "No workflow gate bypass.",
    ]:
        assert term in content
