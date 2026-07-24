from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.acceptance.candidate_service import (
    BOUNDING_PILOT_STATUSES,
    REQUIRED_BRAND_SLUGS,
)
from src.application.acceptance.controlled_snapshot_models import (
    PilotEvidenceSnapshotRequest,
)
from src.application.acceptance.controlled_start_service import (
    ControlledPilotStartService,
)
from src.application.acceptance.models import EvidenceCategory
from src.application.acceptance.service import (
    CONTENT_CATEGORIES,
    AcceptancePilotError,
    _digest,
)
from src.application.acceptance.validated_service import (
    P100_RUNBOOK_RELATIVE_PATH,
    p100_runbook_sha256,
)


_EXPECTED_BRAND_MODES = {
    (brand_slug, production_mode)
    for brand_slug in REQUIRED_BRAND_SLUGS
    for production_mode in ("local_only", "managed_render")
}


class ControlledEvidenceSnapshotService(ControlledPilotStartService):
    """Preview and atomically persist canonical evidence for all four pilot items."""

    def preview(self, *, pilot_id: UUID) -> dict[str, Any]:
        current_runbook_sha256 = p100_runbook_sha256()
        with self.database.connection() as conn:
            report, _records = self._build_preview(
                conn,
                pilot_id=pilot_id,
                current_runbook_sha256=current_runbook_sha256,
                lock=False,
            )
        return report

    def snapshot(
        self,
        *,
        pilot_id: UUID,
        request: PilotEvidenceSnapshotRequest,
        actor: str,
    ) -> dict[str, Any]:
        current_runbook_sha256 = p100_runbook_sha256()
        if request.runbook_sha256 != current_runbook_sha256:
            raise AcceptancePilotError(
                "pilot_snapshot_runbook_digest_mismatch",
                details={
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "expected_sha256": current_runbook_sha256,
                },
            )

        with self.database.transaction() as conn:
            self._require_any_role(conn, actor, {"admin", "reviewer"})
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (str(pilot_id),),
            )
            conn.execute(
                "LOCK TABLE football_brief.acceptance_pilot_items "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
            report, records = self._build_preview(
                conn,
                pilot_id=pilot_id,
                current_runbook_sha256=current_runbook_sha256,
                lock=True,
            )
            self._verify_snapshot_identity(report=report, request=request)
            if not report["snapshot_ready"]:
                raise AcceptancePilotError(
                    "pilot_not_ready_for_evidence_snapshot",
                    details={"blockers": report["blockers"]},
                )

            replay = conn.execute(
                """SELECT count(*) AS event_count,
                          count(DISTINCT pilot_item_id) AS item_count
                   FROM football_brief.acceptance_pilot_events
                   WHERE pilot_id=%s AND event='item_evaluated'
                     AND details->>'snapshot_kind'='controlled_batch'
                     AND details->>'snapshot_sha256'=%s""",
                (pilot_id, report["snapshot_sha256"]),
            ).fetchone()
            if int(replay["item_count"]) == 4:
                pilot = conn.execute(
                    "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s",
                    (pilot_id,),
                ).fetchone()
                items = conn.execute(
                    """SELECT * FROM football_brief.acceptance_pilot_items
                       WHERE pilot_id=%s ORDER BY brand_id,production_mode,id""",
                    (pilot_id,),
                ).fetchall()
                return {
                    "ok": report["all_content_passed"],
                    "kind": "p100_controlled_evidence_snapshot",
                    "reused": True,
                    "snapshot_sha256": report["snapshot_sha256"],
                    "pilot": dict(pilot),
                    "items": [dict(row) for row in items],
                    "evidence_inserted": 0,
                    "evidence_reused": len(CONTENT_CATEGORIES) * 4,
                    "preview": report,
                }

            before_count = int(
                conn.execute(
                    """SELECT count(*) AS count
                       FROM football_brief.acceptance_pilot_evidence ape
                       JOIN football_brief.acceptance_pilot_items api
                         ON api.id=ape.pilot_item_id
                       WHERE api.pilot_id=%s""",
                    (pilot_id,),
                ).fetchone()["count"]
            )

            evaluated_items: list[dict[str, Any]] = []
            blocked_items = 0
            for record in records:
                item = record["item"]
                checks = record["checks"]
                for category in CONTENT_CATEGORIES:
                    self._record_evidence(
                        conn,
                        item_id=item["id"],
                        category=category,
                        result=checks[category],
                        actor=actor,
                    )
                staging = checks[EvidenceCategory.STAGING_DELIVERY]
                staging_id = (
                    staging["details"].get("delivery_request_id")
                    if staging["passed"]
                    else None
                )
                passed = all(
                    checks[category]["passed"] for category in CONTENT_CATEGORIES
                )
                if not passed:
                    blocked_items += 1
                updated = conn.execute(
                    """UPDATE football_brief.acceptance_pilot_items
                       SET status=%s,
                           staging_delivery_request_id=COALESCE(%s,staging_delivery_request_id)
                       WHERE id=%s RETURNING *""",
                    ("passed" if passed else "blocked", staging_id, item["id"]),
                ).fetchone()
                evaluated_items.append(dict(updated))
                self._event(
                    conn,
                    pilot_id,
                    item["id"],
                    "item_evaluated",
                    actor,
                    {
                        "snapshot_kind": "controlled_batch",
                        "snapshot_sha256": report["snapshot_sha256"],
                        "passed": passed,
                        "passed_categories": sum(
                            1
                            for category in CONTENT_CATEGORIES
                            if checks[category]["passed"]
                        ),
                        "required_categories": len(CONTENT_CATEGORIES),
                    },
                )

            pilot = conn.execute(
                "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s FOR UPDATE",
                (pilot_id,),
            ).fetchone()
            if blocked_items and pilot["status"] == "running":
                pilot = conn.execute(
                    """UPDATE football_brief.acceptance_pilots
                       SET status='blocked'
                       WHERE id=%s AND status='running' RETURNING *""",
                    (pilot_id,),
                ).fetchone()
                self._event(
                    conn,
                    pilot_id,
                    None,
                    "pilot_blocked",
                    actor,
                    {
                        "reason": "controlled_evidence_snapshot_incomplete",
                        "snapshot_sha256": report["snapshot_sha256"],
                        "blocked_items": blocked_items,
                    },
                )

            after_count = int(
                conn.execute(
                    """SELECT count(*) AS count
                       FROM football_brief.acceptance_pilot_evidence ape
                       JOIN football_brief.acceptance_pilot_items api
                         ON api.id=ape.pilot_item_id
                       WHERE api.pilot_id=%s""",
                    (pilot_id,),
                ).fetchone()["count"]
            )

        inserted = after_count - before_count
        total = len(CONTENT_CATEGORIES) * 4
        return {
            "ok": report["all_content_passed"],
            "kind": "p100_controlled_evidence_snapshot",
            "reused": False,
            "snapshot_sha256": report["snapshot_sha256"],
            "pilot": dict(pilot),
            "items": evaluated_items,
            "evidence_inserted": inserted,
            "evidence_reused": total - inserted,
            "preview": report,
        }

    @staticmethod
    def _verify_snapshot_identity(
        *,
        report: dict[str, Any],
        request: PilotEvidenceSnapshotRequest,
    ) -> None:
        expected = {
            "bootstrap_request_sha256": report["bootstrap_request_sha256"],
            "controlled_start_event_sha256": report[
                "controlled_start_event_sha256"
            ],
            "runbook_sha256": report["runbook"]["sha256"],
            "snapshot_sha256": report["snapshot_sha256"],
            "started_at": report["started_at"],
        }
        provided = {
            "bootstrap_request_sha256": request.bootstrap_request_sha256,
            "controlled_start_event_sha256": request.controlled_start_event_sha256,
            "runbook_sha256": request.runbook_sha256,
            "snapshot_sha256": request.snapshot_sha256,
            "started_at": request.started_at,
        }
        mismatches = {
            key: {"expected": expected[key], "provided": provided[key]}
            for key in expected
            if provided[key] != expected[key]
        }
        if mismatches:
            raise AcceptancePilotError(
                "pilot_snapshot_identity_mismatch",
                details={"mismatches": mismatches},
            )

    def _build_preview(
        self,
        conn: Any,
        *,
        pilot_id: UUID,
        current_runbook_sha256: str,
        lock: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        pilot_sql = "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s"
        if lock:
            pilot_sql += " FOR UPDATE"
        pilot = conn.execute(pilot_sql, (pilot_id,)).fetchone()
        if not pilot:
            raise AcceptancePilotError("pilot_not_found")

        policy = pilot["acceptance_policy"] or {}
        controlled = policy.get("bootstrap_kind") == "controlled_draft"
        bootstrap_request_sha256 = policy.get("bootstrap_request_sha256")
        start_event_row = conn.execute(
            """SELECT actor,details,created_at
               FROM football_brief.acceptance_pilot_events
               WHERE pilot_id=%s AND event='pilot_started'
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (pilot_id,),
        ).fetchone()
        start_event = None
        controlled_start_event_sha256 = None
        if start_event_row:
            details = start_event_row["details"] or {}
            start_event = {
                "actor": start_event_row["actor"],
                "created_at": start_event_row["created_at"],
                "details": details,
            }
            controlled_start_event_sha256 = _digest(start_event)
        controlled_start = bool(
            start_event
            and start_event["details"].get("start_mode") == "controlled"
            and start_event["details"].get("bootstrap_request_sha256")
            == bootstrap_request_sha256
            and start_event["details"].get("runbook_sha256")
            == current_runbook_sha256
            and pilot["started_by"] == start_event["actor"]
            and pilot["started_at"] is not None
        )

        items = conn.execute(
            """SELECT api.*,b.slug AS brand_slug,b.display_name AS brand_name
               FROM football_brief.acceptance_pilot_items api
               JOIN football_brief.brands b ON b.id=api.brand_id
               WHERE api.pilot_id=%s
               ORDER BY b.slug,api.production_mode,api.portfolio_content_id""",
            (pilot_id,),
        ).fetchall()
        content_ids = [item["portfolio_content_id"] for item in items]
        content_sql = (
            "SELECT id,version FROM football_brief.portfolio_content "
            "WHERE id=ANY(%s::uuid[]) ORDER BY id"
        )
        if lock:
            content_sql += " FOR SHARE"
        content_rows = (
            conn.execute(content_sql, (content_ids,)).fetchall()
            if content_ids
            else []
        )
        current_versions = {
            row["id"]: int(row["version"]) for row in content_rows
        }

        brand_counts: dict[str, int] = {}
        brand_modes: set[tuple[str, str]] = set()
        live_required_count = 0
        stale_items: list[dict[str, Any]] = []
        reports: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        for item in items:
            brand_slug = item["brand_slug"]
            brand_counts[brand_slug] = brand_counts.get(brand_slug, 0) + 1
            brand_modes.add((brand_slug, item["production_mode"]))
            live_required_count += int(bool(item["live_delivery_evidence_required"]))
            current_version = current_versions.get(item["portfolio_content_id"])
            current = current_version == int(item["content_version"])
            if not current:
                stale_items.append(
                    {
                        "pilot_item_id": str(item["id"]),
                        "portfolio_content_id": str(item["portfolio_content_id"]),
                        "bound_version": int(item["content_version"]),
                        "current_version": current_version,
                    }
                )
            checks = self._system_checks(conn, item)
            category_reports = [
                {
                    "category": category.value,
                    "passed": bool(checks[category]["passed"]),
                    "subject_type": checks[category]["subject_type"],
                    "subject_id": checks[category]["subject_id"],
                    "subject_version": checks[category].get("subject_version"),
                    "details_sha256": _digest(checks[category]["details"]),
                }
                for category in CONTENT_CATEGORIES
            ]
            all_passed = current and all(
                entry["passed"] for entry in category_reports
            )
            reports.append(
                {
                    "pilot_item_id": str(item["id"]),
                    "brand_id": str(item["brand_id"]),
                    "brand_slug": brand_slug,
                    "portfolio_content_id": str(item["portfolio_content_id"]),
                    "content_version": int(item["content_version"]),
                    "production_mode": item["production_mode"],
                    "current_version": current_version,
                    "current": current,
                    "all_content_passed": all_passed,
                    "passed_categories": sum(
                        1 for entry in category_reports if entry["passed"]
                    ),
                    "required_categories": len(CONTENT_CATEGORIES),
                    "categories": category_reports,
                }
            )
            records.append({"item": item, "checks": checks})

        scope_ready = (
            len(items) == 4
            and set(brand_counts) == set(REQUIRED_BRAND_SLUGS)
            and all(brand_counts.get(slug) == 2 for slug in REQUIRED_BRAND_SLUGS)
            and brand_modes == _EXPECTED_BRAND_MODES
            and live_required_count == 1
        )
        duplicate_rows = conn.execute(
            """SELECT api.id AS pilot_item_id,api.portfolio_content_id,
                      api.content_version,ap.id AS other_pilot_id,
                      ap.pilot_key,ap.version AS pilot_version,
                      ap.status AS pilot_status
               FROM football_brief.acceptance_pilot_items api
               JOIN football_brief.acceptance_pilots ap ON ap.id=api.pilot_id
               WHERE api.pilot_id<>%s
                 AND ap.status=ANY(%s::text[])
                 AND EXISTS (
                     SELECT 1 FROM football_brief.acceptance_pilot_items own
                     WHERE own.pilot_id=%s
                       AND own.portfolio_content_id=api.portfolio_content_id
                       AND own.content_version=api.content_version
                 )
               ORDER BY ap.created_at,ap.id,api.id""",
            (pilot_id, sorted(BOUNDING_PILOT_STATUSES), pilot_id),
        ).fetchall()
        duplicate_bindings = [
            {
                "pilot_item_id": str(row["pilot_item_id"]),
                "portfolio_content_id": str(row["portfolio_content_id"]),
                "content_version": int(row["content_version"]),
                "other_pilot_id": str(row["other_pilot_id"]),
                "pilot_key": row["pilot_key"],
                "pilot_version": int(row["pilot_version"]),
                "pilot_status": row["pilot_status"],
            }
            for row in duplicate_rows
        ]

        snapshot_payload = {
            "pilot_id": str(pilot_id),
            "pilot_version": int(pilot["version"]),
            "bootstrap_request_sha256": bootstrap_request_sha256,
            "controlled_start_event_sha256": controlled_start_event_sha256,
            "runbook_sha256": current_runbook_sha256,
            "started_at": pilot["started_at"],
            "items": reports,
        }
        snapshot_sha256 = _digest(snapshot_payload)
        snapshot_ready = bool(
            pilot["status"] in {"running", "blocked"}
            and controlled
            and controlled_start
            and scope_ready
            and not stale_items
            and not duplicate_bindings
        )
        all_content_passed = bool(reports) and all(
            report["all_content_passed"] for report in reports
        )
        blockers: list[dict[str, Any]] = []
        if pilot["status"] not in {"running", "blocked"}:
            blockers.append(
                {"code": "pilot_snapshot_status_invalid", "status": pilot["status"]}
            )
        if not controlled:
            blockers.append({"code": "pilot_not_controlled_bootstrap"})
        if not controlled_start:
            blockers.append({"code": "pilot_controlled_start_evidence_invalid"})
        if not scope_ready:
            blockers.append(
                {
                    "code": "pilot_snapshot_scope_invalid",
                    "item_count": len(items),
                    "brand_counts": brand_counts,
                    "brand_modes": [
                        {"brand_slug": brand, "production_mode": mode}
                        for brand, mode in sorted(brand_modes)
                    ],
                    "live_required_count": live_required_count,
                }
            )
        if stale_items:
            blockers.append(
                {"code": "pilot_snapshot_content_version_stale", "items": stale_items}
            )
        if duplicate_bindings:
            blockers.append(
                {"code": "pilot_snapshot_duplicate_binding", "bindings": duplicate_bindings}
            )

        report = {
            "ok": True,
            "kind": "p100_controlled_evidence_preview",
            "pilot_id": str(pilot_id),
            "pilot_key": pilot["pilot_key"],
            "pilot_version": int(pilot["version"]),
            "pilot_status": pilot["status"],
            "started_by": pilot["started_by"],
            "started_at": pilot["started_at"],
            "brand_ids": sorted({str(item["brand_id"]) for item in items}),
            "bootstrap_request_sha256": bootstrap_request_sha256,
            "controlled_start_event_sha256": controlled_start_event_sha256,
            "runbook": {
                "path": P100_RUNBOOK_RELATIVE_PATH,
                "sha256": current_runbook_sha256,
            },
            "scope": {
                "passed": scope_ready,
                "item_count": len(items),
                "brand_counts": brand_counts,
                "brand_modes": [
                    {"brand_slug": brand, "production_mode": mode}
                    for brand, mode in sorted(brand_modes)
                ],
                "live_required_count": live_required_count,
            },
            "items": reports,
            "duplicate_bindings": duplicate_bindings,
            "snapshot_ready": snapshot_ready,
            "all_content_passed": all_content_passed,
            "snapshot_sha256": snapshot_sha256,
            "blockers": blockers,
        }
        return report, records


__all__ = ["ControlledEvidenceSnapshotService"]
