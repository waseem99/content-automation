from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from src.application.acceptance.candidate_service import (
    BOUNDING_PILOT_STATUSES,
    REQUIRED_BRAND_SLUGS,
    SELECTION_CATEGORIES,
)
from src.application.acceptance.controlled_start_models import (
    PilotControlledStartRequest,
)
from src.application.acceptance.service import AcceptancePilotError
from src.application.acceptance.start_guarded_service import (
    StartGuardedAcceptancePilotService,
)
from src.application.acceptance.validated_service import (
    P100_RUNBOOK_RELATIVE_PATH,
    p100_runbook_sha256,
)


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_BRAND_MODES = {
    (brand_slug, production_mode)
    for brand_slug in REQUIRED_BRAND_SLUGS
    for production_mode in ("local_only", "managed_render")
}


class ControlledPilotStartService(StartGuardedAcceptancePilotService):
    """Revalidate and atomically start a controlled P100 bootstrap."""

    def pilot_brand_ids(self, *, pilot_id: UUID) -> list[str]:
        with self.database.connection() as conn:
            pilot = conn.execute(
                "SELECT id FROM football_brief.acceptance_pilots WHERE id=%s",
                (pilot_id,),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_found")
            rows = conn.execute(
                """SELECT DISTINCT brand_id
                   FROM football_brief.acceptance_pilot_items
                   WHERE pilot_id=%s ORDER BY brand_id""",
                (pilot_id,),
            ).fetchall()
        return [str(row["brand_id"]) for row in rows]

    def start_readiness(self, *, pilot_id: UUID) -> dict[str, Any]:
        current_runbook_sha256 = p100_runbook_sha256()
        with self.database.connection() as conn:
            return self._evaluate_start_readiness(
                conn,
                pilot_id=pilot_id,
                current_runbook_sha256=current_runbook_sha256,
                lock=False,
            )

    def start_controlled(
        self,
        *,
        pilot_id: UUID,
        request: PilotControlledStartRequest,
        actor: str,
    ) -> dict[str, Any]:
        current_runbook_sha256 = p100_runbook_sha256()
        if request.runbook_sha256 != current_runbook_sha256:
            raise AcceptancePilotError(
                "pilot_start_runbook_digest_mismatch",
                details={
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "expected_sha256": current_runbook_sha256,
                },
            )

        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (str(pilot_id),),
            )
            conn.execute(
                "LOCK TABLE football_brief.acceptance_pilot_items "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
            report = self._evaluate_start_readiness(
                conn,
                pilot_id=pilot_id,
                current_runbook_sha256=current_runbook_sha256,
                lock=True,
            )
            stored_fingerprint = report["bootstrap_request_sha256"]
            if request.bootstrap_request_sha256 != stored_fingerprint:
                raise AcceptancePilotError(
                    "pilot_start_bootstrap_digest_mismatch",
                    details={
                        "expected_sha256": stored_fingerprint,
                        "provided_sha256": request.bootstrap_request_sha256,
                    },
                )

            if report["pilot_status"] == "running":
                event = report["start_event"]
                if (
                    event
                    and event["start_mode"] == "controlled"
                    and event["bootstrap_request_sha256"]
                    == request.bootstrap_request_sha256
                    and event["runbook_sha256"] == request.runbook_sha256
                ):
                    pilot = conn.execute(
                        "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s",
                        (pilot_id,),
                    ).fetchone()
                    return {
                        "ok": True,
                        "kind": "p100_controlled_start",
                        "reused": True,
                        "pilot": dict(pilot),
                        "start_readiness": report,
                    }
                raise AcceptancePilotError(
                    "pilot_controlled_start_replay_mismatch",
                    details={"pilot_id": str(pilot_id)},
                )

            if not report["can_start"]:
                raise AcceptancePilotError(
                    "pilot_not_ready_to_start",
                    details={"blockers": report["blockers"]},
                )

            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='running',started_by=%s,started_at=now()
                   WHERE id=%s AND status='draft'
                   RETURNING *""",
                (actor, pilot_id),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_startable")
            self._event(
                conn,
                pilot_id,
                None,
                "pilot_started",
                actor,
                {
                    "start_mode": "controlled",
                    "bootstrap_request_sha256": request.bootstrap_request_sha256,
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "runbook_sha256": request.runbook_sha256,
                },
            )

        return {
            "ok": True,
            "kind": "p100_controlled_start",
            "reused": False,
            "pilot": dict(pilot),
            "start_readiness": report,
        }

    def _evaluate_start_readiness(
        self,
        conn: Any,
        *,
        pilot_id: UUID,
        current_runbook_sha256: str,
        lock: bool,
    ) -> dict[str, Any]:
        pilot_sql = "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s"
        if lock:
            pilot_sql += " FOR UPDATE"
        pilot = conn.execute(pilot_sql, (pilot_id,)).fetchone()
        if not pilot:
            raise AcceptancePilotError("pilot_not_found")

        policy = pilot["acceptance_policy"] or {}
        bootstrap_kind = policy.get("bootstrap_kind")
        bootstrap_request_sha256 = policy.get("bootstrap_request_sha256")
        controlled = (
            bootstrap_kind == "controlled_draft"
            and isinstance(bootstrap_request_sha256, str)
            and bool(_DIGEST_RE.fullmatch(bootstrap_request_sha256))
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
        item_reports: list[dict[str, Any]] = []
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
            selection = [
                {
                    "category": category.value,
                    "passed": bool(checks[category]["passed"]),
                    "subject_type": checks[category]["subject_type"],
                    "subject_id": checks[category]["subject_id"],
                    "subject_version": checks[category].get("subject_version"),
                }
                for category in SELECTION_CATEGORIES
            ]
            item_reports.append(
                {
                    "pilot_item_id": str(item["id"]),
                    "brand_id": str(item["brand_id"]),
                    "brand_slug": brand_slug,
                    "portfolio_content_id": str(item["portfolio_content_id"]),
                    "content_version": int(item["content_version"]),
                    "production_mode": item["production_mode"],
                    "current_version": current_version,
                    "current": current,
                    "selection_ready": current
                    and all(entry["passed"] for entry in selection),
                    "selection": selection,
                }
            )

        scope_ready = (
            len(items) == 4
            and set(brand_counts) == set(REQUIRED_BRAND_SLUGS)
            and all(brand_counts.get(slug) == 2 for slug in REQUIRED_BRAND_SLUGS)
            and brand_modes == _EXPECTED_BRAND_MODES
            and live_required_count == 1
        )
        items_ready = bool(items) and all(
            report["selection_ready"] for report in item_reports
        )

        duplicate_rows = conn.execute(
            """SELECT api.id AS pilot_item_id,api.portfolio_content_id,
                      api.content_version,ap.id AS other_pilot_id,
                      ap.pilot_key,ap.version AS pilot_version,ap.status AS pilot_status
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
        duplicate_bindings = [dict(row) for row in duplicate_rows]

        clean_counts = conn.execute(
            """SELECT
                 (SELECT count(*) FROM football_brief.acceptance_pilot_evidence ape
                   JOIN football_brief.acceptance_pilot_items api
                     ON api.id=ape.pilot_item_id
                  WHERE api.pilot_id=%s) AS evidence_count,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_signoffs
                  WHERE pilot_id=%s) AS signoff_count,
                 (SELECT count(*) FROM football_brief.acceptance_live_delivery_evidence
                  WHERE pilot_id=%s) AS live_result_count,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_defects
                  WHERE pilot_id=%s AND severity IN ('major','critical')
                    AND status='open') AS blocking_defect_count""",
            (pilot_id, pilot_id, pilot_id, pilot_id),
        ).fetchone()
        clean_draft = all(
            int(clean_counts[key]) == 0
            for key in (
                "evidence_count",
                "signoff_count",
                "live_result_count",
                "blocking_defect_count",
            )
        )

        start_event_row = conn.execute(
            """SELECT actor,details,created_at
               FROM football_brief.acceptance_pilot_events
               WHERE pilot_id=%s AND event='pilot_started'
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (pilot_id,),
        ).fetchone()
        start_event = None
        if start_event_row:
            details = start_event_row["details"] or {}
            start_event = {
                "actor": start_event_row["actor"],
                "created_at": start_event_row["created_at"],
                "start_mode": details.get("start_mode"),
                "bootstrap_request_sha256": details.get(
                    "bootstrap_request_sha256"
                ),
                "runbook_sha256": details.get("runbook_sha256"),
            }

        can_start = (
            pilot["status"] == "draft"
            and controlled
            and scope_ready
            and items_ready
            and not duplicate_bindings
            and clean_draft
        )
        blockers: list[dict[str, Any]] = []
        if pilot["status"] != "draft":
            blockers.append(
                {"code": "pilot_not_draft", "status": pilot["status"]}
            )
        if not controlled:
            blockers.append(
                {
                    "code": "pilot_not_controlled_bootstrap",
                    "bootstrap_kind": bootstrap_kind,
                }
            )
        if not scope_ready:
            blockers.append(
                {
                    "code": "pilot_start_scope_invalid",
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
                {"code": "pilot_start_content_version_stale", "items": stale_items}
            )
        for report in item_reports:
            missing = [
                entry["category"]
                for entry in report["selection"]
                if not entry["passed"]
            ]
            if missing:
                blockers.append(
                    {
                        "code": "pilot_start_selection_evidence_incomplete",
                        "pilot_item_id": report["pilot_item_id"],
                        "missing_categories": missing,
                    }
                )
        if duplicate_bindings:
            blockers.append(
                {
                    "code": "pilot_start_duplicate_binding",
                    "bindings": duplicate_bindings,
                }
            )
        if not clean_draft:
            blockers.append(
                {
                    "code": "pilot_start_draft_not_clean",
                    **{key: int(value) for key, value in dict(clean_counts).items()},
                }
            )

        return {
            "ok": True,
            "kind": "p100_controlled_start_readiness",
            "pilot_id": str(pilot_id),
            "pilot_key": pilot["pilot_key"],
            "pilot_version": int(pilot["version"]),
            "pilot_status": pilot["status"],
            "started_by": pilot.get("started_by"),
            "started_at": pilot["started_at"],
            "brand_ids": sorted({str(item["brand_id"]) for item in items}),
            "controlled_bootstrap": controlled,
            "bootstrap_request_sha256": bootstrap_request_sha256,
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
            "items": item_reports,
            "duplicate_bindings": duplicate_bindings,
            "clean_draft": {
                "passed": clean_draft,
                **{key: int(value) for key, value in dict(clean_counts).items()},
            },
            "runbook": {
                "path": P100_RUNBOOK_RELATIVE_PATH,
                "sha256": current_runbook_sha256,
            },
            "start_event": start_event,
            "can_start": can_start,
            "blockers": blockers,
        }


__all__ = ["ControlledPilotStartService"]
