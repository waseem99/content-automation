from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.operations.staged_acceptance_report import (
    EXPECTED_GATES,
    StagedReportError,
    build_report,
    load_manifest,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[2]


def _manifest() -> dict:
    measurements = {
        "campaign_intake": {"items": 10000, "duplicate_items": 0},
        "autopilot": {"items": 1000, "ready": 950, "hard_blocks": 50, "human_exceptions": 0},
        "dag_workers": {"tasks": 1000000, "workers": 100, "recovered_leases": 100},
        "storage": {"assets": 50000, "locations": 100000, "recovered_local_copies": 1},
        "campaign_grid": {"records": 1200, "matching_retry_limit": 20000},
        "mass_operations": {"items": 1000, "exact_result_rows": 1000},
        "database_scale": {"items": 10000, "checks": 1000000, "duplicate_checks": 0},
        "hybrid_routing": {"master_seconds": 120, "paid_attempts": 0},
    }
    return {
        "report_key": "p131-test-report",
        "gates": {
            gate: {
                "conclusion": "success",
                "pull_request": index + 800,
                "merge_commit": "a" * 40,
                "workflow_run": index + 30000000,
                "measurements": measurements[gate],
            }
            for index, gate in enumerate(sorted(EXPECTED_GATES))
        },
        "unresolved_renderer_measurements": [
            "accepted real generated seconds per GPU hour",
            "real route acceptance and retry rates",
        ],
    }


def test_p131_requires_exact_green_gate_set(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_manifest(path)
    assert set(loaded["gates"]) == EXPECTED_GATES

    manifest["gates"]["storage"]["conclusion"] = "failure"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StagedReportError, match="gate_not_green:storage"):
        load_manifest(path)


def test_p131_proves_control_plane_but_not_renderer_capacity() -> None:
    report = build_report(_manifest())
    assert report["central_ecosystem_verdict"] == "proven"
    assert report["monthly_renderer_verdict"] == "not_yet_proven"
    assert report["measurements"]["control_plane_items"] == 10000
    assert report["measurements"]["control_plane_checks"] == 1000000
    assert report["measurements"]["dag_tasks"] == 1000000
    assert report["measurements"]["storage_locations"] == 100000
    assert report["measurements"]["mass_operation_items"] == 1000
    assert report["report_sha256"]
    markdown = render_markdown(report)
    assert "Central database-native ecosystem: PROVEN" in markdown
    assert "renderer capacity: NOT YET PROVEN" in markdown
    assert "does not claim" in markdown


def test_p131_rejects_missing_renderer_bottlenecks() -> None:
    manifest = _manifest()
    manifest["unresolved_renderer_measurements"] = []
    with pytest.raises(StagedReportError, match="renderer_bottlenecks_must_be_explicit"):
        build_report(manifest)


def test_p131_migration_keeps_completed_report_immutable() -> None:
    migration = (ROOT / "migrations/0108_p131_staged_acceptance_closeout.sql").read_text()
    assert "staged_acceptance_reports" in migration
    assert "monthly_renderer_verdict" in migration
    assert "control_plane_checks>=1000000" in migration
    assert "dag_tasks>=1000000" in migration
    assert "storage_locations>=100000" in migration
    assert "Completed staged acceptance reports are immutable" in migration
