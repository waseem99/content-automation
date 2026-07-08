from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p21-step-03.md")


def test_p21_rollback_restore_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p21-step-01.md",
        "docs/operations/p21-step-02.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p20-readiness-report.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-05.md",
    ]:
        assert term in content


def test_p21_rollback_restore_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This rollback and restore evidence review is documentation-only.",
        "execute rollback",
        "execute restore",
        "restore production data",
        "change production configuration",
        "approve rollback",
        "approve restore",
        "approve production launch",
        "schedule recovery activity",
        "bypass workflow gates",
        "export restricted evidence",
    ]:
        assert term in content


def test_p21_rollback_restore_documents_decision_fields_approval_and_validation() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "rollback decision question",
        "restore decision question",
        "release owner review",
        "incident owner review",
        "evidence owner review",
        "affected scope summary",
        "rollback route placeholder",
        "restore route placeholder",
        "follow-up issue route",
        "evidence item identifier",
        "decision type",
        "simulated scenario",
        "decision owner",
        "incident owner when applicable",
        "evidence sensitivity",
        "validation requirement",
        "approval status",
        "not approved",
        "review only",
        "decision pending",
        "approved placeholder only",
        "blocked by guardrail",
        "No status may imply live rollback or live restore.",
        "exact-head CI evidence is referenced when implementation is involved",
        "rollback and restore are not executed",
        "follow-up issue is created when implementation is needed",
    ]:
        assert term in content


def test_p21_rollback_restore_documents_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "summarized rollback review note",
        "summarized restore review note",
        "summarized owner review note",
        "summarized validation note",
        "evidence archive entry name",
        "secret values",
        "private runtime values",
        "customer data exports",
        "production data dumps",
        "rendered rollback material",
        "scheduled restore outputs",
        "decision type is missing",
        "affected scope summary is missing",
        "release owner is missing for rollback or restore decision",
        "live rollback is implied",
        "live restore is implied",
        "production data restore is implied",
        "production change is implied",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
