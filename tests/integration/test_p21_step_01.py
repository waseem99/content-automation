from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p21-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p21_recovery_drill_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p20-readiness-report.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-readiness-report.md",
    ]:
        assert term in content


def test_p21_recovery_drill_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This recovery drill plan is documentation-only.",
        "execute live recovery",
        "execute live rollback",
        "restore production data",
        "change production configuration",
        "notify external contacts",
        "schedule drill automation",
        "approve production launch",
        "bypass workflow gates",
        "publish drill evidence",
        "export restricted evidence",
    ]:
        assert term in content


def test_p21_recovery_drill_documents_assumptions_roles_scenarios_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "all actions are simulated",
        "evidence is summary-only",
        "no customer data is copied",
        "no production systems are changed",
        "drill facilitator",
        "operator owner",
        "support owner",
        "incident owner",
        "release owner",
        "evidence owner",
        "reviewer",
        "observer",
        "failed exact-head CI during release preparation",
        "operator detects missing owner",
        "support case suggests customer impact",
        "security incident suggests restricted evidence exposure",
        "rollback decision question appears",
        "restore decision question appears",
        "blackout window conflict appears",
        "workflow gate bypass is requested",
        "drill record identifier",
        "scenario name",
        "simulated trigger",
        "expected response route",
        "actual response summary",
        "pass/fail result",
        "follow-up route",
        "closure criteria",
    ]:
        assert term in content


def test_p21_recovery_drill_documents_pass_fail_evidence_stops_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "scenario is classified",
        "owner is identified",
        "restricted values are not recorded",
        "no live recovery action is taken",
        "follow-up issue is proposed when implementation is needed",
        "restricted value is copied",
        "live recovery action is implied",
        "external notification is implied",
        "escalation is skipped for high-risk scenario",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "summarized drill note",
        "evidence archive entry name",
        "secret values",
        "private runtime values",
        "customer data exports",
        "external package exports",
        "drill record identifier is missing",
        "live recovery is implied",
        "live rollback is implied",
        "production change is implied",
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

    assert "tests/integration/test_p21_step_*.py" in harness
