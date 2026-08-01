from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


EXPECTED_GATES = {
    "campaign_intake",
    "autopilot",
    "dag_workers",
    "storage",
    "campaign_grid",
    "mass_operations",
    "database_scale",
    "hybrid_routing",
}


class StagedReportError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise StagedReportError("manifest_must_be_object")
    gates = manifest.get("gates")
    if not isinstance(gates, dict) or set(gates) != EXPECTED_GATES:
        raise StagedReportError(
            f"manifest_gates_must_equal:{sorted(EXPECTED_GATES)}"
        )
    for key, gate in gates.items():
        if not isinstance(gate, dict):
            raise StagedReportError(f"gate_must_be_object:{key}")
        if gate.get("conclusion") != "success":
            raise StagedReportError(f"gate_not_green:{key}")
        for required in ("pull_request", "merge_commit", "workflow_run", "measurements"):
            if not gate.get(required):
                raise StagedReportError(f"gate_missing_{required}:{key}")
    return manifest


def build_report(manifest: dict[str, Any]) -> dict[str, Any]:
    gates = manifest["gates"]
    scale = gates["database_scale"]["measurements"]
    autopilot = gates["autopilot"]["measurements"]
    dag = gates["dag_workers"]["measurements"]
    storage = gates["storage"]["measurements"]
    mass = gates["mass_operations"]["measurements"]
    hybrid = gates["hybrid_routing"]["measurements"]

    proven_capabilities = [
        "database-native 10,000-item campaign intake and idempotent activation",
        "1,000-item automatic pre-generation with grouped hard blockers",
        "1,000,000 retained orchestration tasks with 100 capability-aware workers",
        "100,000 canonical local/Google Drive location records and verified recovery",
        "20,000-row campaign operations grid and 1,000-item exact mass action",
        "120-second exact hybrid route plan with deterministic/reused/local/manual fallbacks",
        "PostgreSQL as the sole workflow state database",
    ]
    unresolved = list(manifest.get("unresolved_renderer_measurements") or [])
    if not unresolved:
        raise StagedReportError("renderer_bottlenecks_must_be_explicit")

    report = {
        "schema": "staged-acceptance-closeout/v1",
        "report_key": manifest["report_key"],
        "central_ecosystem_verdict": "proven",
        "monthly_renderer_verdict": "not_yet_proven",
        "measurements": {
            "control_plane_items": int(scale["items"]),
            "control_plane_checks": int(scale["checks"]),
            "dag_tasks": int(dag["tasks"]),
            "dag_workers": int(dag["workers"]),
            "autopilot_items": int(autopilot["items"]),
            "autopilot_ready": int(autopilot["ready"]),
            "grouped_hard_blocks": int(autopilot["hard_blocks"]),
            "storage_assets": int(storage["assets"]),
            "storage_locations": int(storage["locations"]),
            "mass_operation_items": int(mass["items"]),
            "hybrid_master_seconds": float(hybrid["master_seconds"]),
        },
        "proven_capabilities": proven_capabilities,
        "unresolved_renderer_measurements": unresolved,
        "evidence": gates,
        "management_summary": {
            "central_ecosystem": (
                "Proven for database-native campaign intake, automatic pre-generation, "
                "grouped exceptions, horizontally scalable task orchestration, canonical "
                "local/Drive storage, campaign operations and immutable generation packages."
            ),
            "renderer_capacity": (
                "Not yet proven for 10,000–20,000 completed real videos per month. "
                "No database/control-plane benchmark is interpreted as GPU or provider throughput."
            ),
            "automatic_paid_generation": False,
            "automatic_public_publishing": False,
        },
    }

    minimums = {
        "control_plane_items": 10_000,
        "control_plane_checks": 1_000_000,
        "dag_tasks": 1_000_000,
        "dag_workers": 100,
        "autopilot_items": 1_000,
        "autopilot_ready": 950,
        "storage_locations": 100_000,
        "mass_operation_items": 1_000,
        "hybrid_master_seconds": 120,
    }
    for key, minimum in minimums.items():
        if report["measurements"][key] < minimum:
            raise StagedReportError(f"measurement_below_minimum:{key}")
    report["report_sha256"] = _sha(report)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    m = report["measurements"]
    evidence = report["evidence"]
    gate_rows = []
    for key in sorted(evidence):
        gate = evidence[key]
        gate_rows.append(
            f"| {key.replace('_', ' ').title()} | #{gate['pull_request']} | "
            f"`{gate['merge_commit'][:12]}` | {gate['workflow_run']} | Success |"
        )
    unresolved = "\n".join(
        f"- {item}" for item in report["unresolved_renderer_measurements"]
    )
    proven = "\n".join(f"- {item}" for item in report["proven_capabilities"])
    return f"""# Final Staged Acceptance Report

## Verdict

**Central database-native ecosystem: PROVEN.**

**10,000–20,000 completed real videos/month renderer capacity: NOT YET PROVEN.**

The control plane can prepare and route work at the required scale. The evidence does not claim that the currently available GPUs, cloud workflows or premium providers can render and creatively accept 10,000–20,000 real completed videos per month.

## Measured acceptance

- Campaign/control-plane items: **{m['control_plane_items']:,}**
- Retained checks: **{m['control_plane_checks']:,}**
- DAG tasks: **{m['dag_tasks']:,}**
- Capability-aware workers: **{m['dag_workers']:,}**
- Automatic pre-generation items: **{m['autopilot_items']:,}**
- Automatically ready packages: **{m['autopilot_ready']:,}**
- Grouped hard blocks: **{m['grouped_hard_blocks']:,}**
- Canonical assets / locations: **{m['storage_assets']:,} / {m['storage_locations']:,}**
- Exact mass-operation items: **{m['mass_operation_items']:,}**
- Exact hybrid master planned: **{m['hybrid_master_seconds']:g} seconds**

## Proven capabilities

{proven}

## Remaining renderer proof

{unresolved}

Until those measurements pass, paid generation remains approval-gated and public publishing remains human-controlled.

## Evidence ledger

| Gate | PR | Merge commit | Workflow run | Result |
|---|---:|---|---:|---|
{chr(10).join(gate_rows)}

Report digest: `{report['report_sha256']}`
"""


def retain_report(
    database: Database,
    *,
    report: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    m = report["measurements"]
    with database.transaction() as conn:
        operator = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if operator is None:
            raise StagedReportError("operator_inactive_or_missing")
        row = conn.execute(
            """INSERT INTO football_brief.staged_acceptance_reports
               (report_key,status,central_ecosystem_verdict,monthly_renderer_verdict,
                control_plane_items,control_plane_checks,dag_tasks,dag_workers,
                autopilot_items,autopilot_ready,grouped_hard_blocks,storage_assets,
                storage_locations,mass_operation_items,hybrid_master_seconds,evidence,
                proven_capabilities,unresolved_renderer_measurements,management_summary,
                report_sha256,created_by,completed_at)
               VALUES (%s,'passed',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,now())
               RETURNING *""",
            (
                report["report_key"],
                report["central_ecosystem_verdict"],
                report["monthly_renderer_verdict"],
                m["control_plane_items"],
                m["control_plane_checks"],
                m["dag_tasks"],
                m["dag_workers"],
                m["autopilot_items"],
                m["autopilot_ready"],
                m["grouped_hard_blocks"],
                m["storage_assets"],
                m["storage_locations"],
                m["mass_operation_items"],
                m["hybrid_master_seconds"],
                _canonical(report["evidence"]),
                _canonical(report["proven_capabilities"]),
                _canonical(report["unresolved_renderer_measurements"]),
                _canonical(report["management_summary"]),
                report["report_sha256"],
                actor,
            ),
        ).fetchone()
    return dict(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the final staged acceptance report")
    parser.add_argument("--manifest", type=Path, default=Path("config/staged-acceptance-evidence.json"))
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--retain", action="store_true")
    parser.add_argument("--actor", default="local-admin")
    args = parser.parse_args()
    report = build_report(load_manifest(args.manifest))
    if args.markdown:
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    if args.retain:
        database = Database(get_database_settings())
        database.open(require_schema=True)
        try:
            retain_report(database, report=report, actor=args.actor)
        finally:
            database.close()
    print(_canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
