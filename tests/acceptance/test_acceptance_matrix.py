from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_DIR = ROOT / "docs" / "acceptance"
MATRIX = ACCEPTANCE_DIR / "scenario-test-matrix.md"


def _feature_scenarios() -> list[str]:
    scenarios: list[str] = []
    for feature_file in sorted(ACCEPTANCE_DIR.glob("phase-*.feature")):
        for line in feature_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("Scenario:"):
                scenarios.append(stripped.removeprefix("Scenario:").strip())
            elif stripped.startswith("Scenario Outline:"):
                scenarios.append(stripped.removeprefix("Scenario Outline:").strip())
    return scenarios


def _matrix_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] != "Feature":
            rows.append(cells)
    return rows


@pytest.mark.acceptance
def test_every_phase_zero_and_one_feature_scenario_is_mapped() -> None:
    scenarios = _feature_scenarios()
    assert scenarios, "No Phase 0/1 feature scenarios were found"
    matrix_text = MATRIX.read_text(encoding="utf-8")
    missing = [scenario for scenario in scenarios if scenario not in matrix_text]
    assert missing == []


@pytest.mark.acceptance
def test_every_matrix_row_points_to_existing_executable_evidence() -> None:
    rows = _matrix_rows()
    assert rows, "Acceptance matrix has no scenario rows"
    unexpected_refs: dict[str, list[str]] = {}
    for _feature, scenario, status, evidence, *_rest in rows:
        assert status in {"automated", "manual"}, f"Unexpected status for {scenario}: {status}"
        refs = re.findall(r"`([^`]+)`", evidence)
        if status == "automated":
            assert refs, f"Automated scenario has no executable evidence: {scenario}"
        for ref in refs:
            if ref.startswith(".github/workflows/"):
                assert (ROOT / ref).exists(), f"Missing workflow evidence for {scenario}: {ref}"
            elif ref.startswith("tests/"):
                assert (ROOT / ref).exists(), f"Missing test evidence for {scenario}: {ref}"
            else:
                unexpected_refs.setdefault(scenario, []).append(ref)
    assert unexpected_refs == {}


@pytest.mark.acceptance
def test_no_manual_only_acceptance_scenario_without_evidence_policy() -> None:
    manual_rows = [row for row in _matrix_rows() if row[2] == "manual"]
    if manual_rows:
        matrix_text = MATRIX.read_text(encoding="utf-8")
        assert "owner" in matrix_text.lower()
        assert "expiry date" in matrix_text.lower()
    assert all(row[3].strip() for row in manual_rows)
