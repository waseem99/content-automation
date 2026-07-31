from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}
NON_BLOCKING_STATUSES = {"PASS", "PASSED", "SKIP", "SKIPPED", "EXEMPT", "NOT_APPLICABLE"}
FINDING_COLLECTIONS = ("Vulnerabilities", "Misconfigurations", "Secrets")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _iter_findings(report: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    results = report.get("Results")
    if not isinstance(results, list) or not results:
        raise ValueError("Trivy report must contain at least one Results entry")

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Every Trivy Results entry must be an object")
        target = _text(result.get("Target"))
        for collection in FINDING_COLLECTIONS:
            findings = result.get(collection, [])
            if findings is None:
                continue
            if not isinstance(findings, list):
                raise ValueError(f"{collection} must be a list")
            for finding in findings:
                if not isinstance(finding, dict):
                    raise ValueError(f"Every {collection} item must be an object")
                yield target, collection, finding


def _normalized_finding(target: str, collection: str, finding: dict[str, Any]) -> dict[str, str]:
    identifier = (
        finding.get("VulnerabilityID")
        or finding.get("ID")
        or finding.get("RuleID")
        or finding.get("Title")
        or "unknown"
    )
    return {
        "target": target,
        "collection": collection,
        "id": _text(identifier),
        "severity": _text(finding.get("Severity")).upper(),
        "status": _text(finding.get("Status")).upper(),
        "package": _text(finding.get("PkgName") or finding.get("PackageName")),
        "installed_version": _text(finding.get("InstalledVersion")),
        "fixed_version": _text(finding.get("FixedVersion")),
        "title": _text(finding.get("Title") or finding.get("Description")),
        "primary_url": _text(finding.get("PrimaryURL")),
    }


def evaluate_report(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("Trivy report root must be an object")

    findings: list[dict[str, str]] = []
    blocking: list[dict[str, str]] = []

    for target, collection, raw in _iter_findings(report):
        finding = _normalized_finding(target, collection, raw)
        findings.append(finding)
        if (
            finding["severity"] in BLOCKING_SEVERITIES
            and finding["status"] not in NON_BLOCKING_STATUSES
        ):
            blocking.append(finding)

    return {
        "ok": not blocking,
        "schema_version": report.get("SchemaVersion"),
        "trivy_version": (report.get("Trivy") or {}).get("Version")
        if isinstance(report.get("Trivy"), dict)
        else None,
        "result_count": len(report["Results"]),
        "finding_count": len(findings),
        "blocking_count": len(blocking),
        "blocking_severities": sorted(BLOCKING_SEVERITIES),
        "blocking_findings": blocking,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce the P99 Trivy JSON policy.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        summary = evaluate_report(report)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        summary = {
            "ok": False,
            "blocking_count": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
