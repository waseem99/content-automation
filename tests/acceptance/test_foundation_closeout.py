from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "operations" / "foundation-readiness-report.md"
CHECKLIST = ROOT / "docs" / "operations" / "foundation-closeout-checklist.md"
MATRIX = ROOT / "docs" / "acceptance" / "scenario-test-matrix.md"


@pytest.mark.acceptance
def test_foundation_readiness_report_covers_all_child_issues_and_delivery_prs() -> None:
    text = REPORT.read_text(encoding="utf-8")
    for issue_number in range(1, 14):
        assert f"#{issue_number}" in text
    for pr_number in (20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32):
        assert f"#{pr_number}" in text
    assert "Phase 0" in text
    assert "Phase 1" in text
    assert "Autonomous publishing | Not enabled" in text
    assert "No content-intelligence" in text


@pytest.mark.acceptance
def test_foundation_checklist_keeps_phase_two_blocked_until_epics_close() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    required_controls = (
        "Canonical asset registry",
        "Rights approvals",
        "Rights gate",
        "Preview and publish manifest modes",
        "Approved voice policy",
        "Provider-generation lineage",
        "Publish quality reports",
        "PostgreSQL migration runner",
        "Workflow events are append-only",
        "Worker idempotency keys",
        "Human review requests",
        "Budget checks",
        "Storage, configuration validation, structured logs",
        "CI applies migrations",
    )
    for control in required_controls:
        assert control in text
    assert "Do not create or merge content-intelligence" in text
    assert "#14" in text and "#15" in text


@pytest.mark.acceptance
def test_closeout_matrix_has_automated_negative_and_traceability_evidence() -> None:
    matrix = MATRIX.read_text(encoding="utf-8")
    negative_signals = (
        "Block an extracted match clip without approved rights",
        "Block an expired licence",
        "Block placeholders in publish mode",
        "Reject an unauthorized cloned voice",
        "Enforce workflow budget",
        "Block publication without a passing quality report",
    )
    for scenario in negative_signals:
        assert scenario in matrix

    traceability_refs = (
        "test_asset_pipeline.py",
        "test_provider_lineage_contracts.py",
        "test_manifest_builder.py",
        "test_quality_package_guard.py",
        "test_flow_events.py",
    )
    for ref in traceability_refs:
        assert ref in matrix

    manual_rows = [line for line in matrix.splitlines() if re.search(r"\|\s*manual\s*\|", line)]
    assert manual_rows == []
