from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "enforce_trivy_report.py"
SPEC = importlib.util.spec_from_file_location("p99_trivy_policy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
evaluate_report = MODULE.evaluate_report


def report_with(collection: str | None = None, finding: dict | None = None) -> dict:
    result: dict = {"Target": "content-automation:test", "Class": "os-pkgs", "Type": "debian"}
    if collection is not None:
        result[collection] = [] if finding is None else [finding]
    return {"SchemaVersion": 2, "Trivy": {"Version": "test"}, "Results": [result]}


def test_clean_inventory_report_passes() -> None:
    summary = evaluate_report(report_with())
    assert summary["ok"] is True
    assert summary["blocking_count"] == 0


def test_high_vulnerability_blocks() -> None:
    summary = evaluate_report(
        report_with(
            "Vulnerabilities",
            {
                "VulnerabilityID": "CVE-TEST-1",
                "Severity": "HIGH",
                "PkgName": "demo",
                "InstalledVersion": "1",
                "FixedVersion": "2",
            },
        )
    )
    assert summary["ok"] is False
    assert summary["blocking_findings"][0]["id"] == "CVE-TEST-1"


def test_critical_secret_blocks() -> None:
    summary = evaluate_report(
        report_with("Secrets", {"RuleID": "private-key", "Severity": "CRITICAL"})
    )
    assert summary["ok"] is False


def test_high_misconfiguration_marked_pass_does_not_block() -> None:
    summary = evaluate_report(
        report_with(
            "Misconfigurations",
            {"ID": "CFG-1", "Severity": "HIGH", "Status": "PASS"},
        )
    )
    assert summary["ok"] is True


def test_medium_finding_does_not_block() -> None:
    summary = evaluate_report(
        report_with(
            "Vulnerabilities",
            {"VulnerabilityID": "CVE-TEST-2", "Severity": "MEDIUM"},
        )
    )
    assert summary["ok"] is True


def test_empty_results_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one Results"):
        evaluate_report({"SchemaVersion": 2, "Results": []})
