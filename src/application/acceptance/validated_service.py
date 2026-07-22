from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.acceptance.models import (
    EvidenceCategory,
    OperationsEvidenceRequest,
    PilotAcceptRequest,
    PilotRetireRequest,
)
from src.application.acceptance.service import (
    CONTENT_CATEGORIES,
    AcceptancePilotError,
    AcceptancePilotService,
    _digest,
)


P100_RUNBOOK_RELATIVE_PATH = "docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md"
OPERATIONS_CATEGORIES = (
    EvidenceCategory.BACKUP_RESTORE,
    EvidenceCategory.WORKER_RESTART,
    EvidenceCategory.RUNBOOK_VALIDATION,
)
REQUIRED_SIGNOFF_ROLES = {"admin", "reviewer", "publisher"}
REQUIRED_BRAND_SLUGS = {"animal-x", "rawr-nation"}


def p100_runbook_path() -> Path:
    return Path(__file__).resolve().parents[3] / P100_RUNBOOK_RELATIVE_PATH


def p100_runbook_sha256() -> str:
    path = p100_runbook_path()
    if not path.is_file():
        raise AcceptancePilotError(
            "pilot_runbook_missing",
            details={"runbook_path": P100_RUNBOOK_RELATIVE_PATH},
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ValidatedAcceptancePilotService(AcceptancePilotService):
    """Acceptance collector with exact canonical subjects and immutable revision recovery."""

    def retire(
        self,
        *,
        pilot_id: UUID,
        request: PilotRetireRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s AND status IN ('running','blocked') RETURNING *""",
                (actor, pilot_id),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_retirable")
            self._event(
                conn,
                pilot_id,
                None,
                "pilot_retired",
                actor,
                {"reason": request.reason},
            )
        return {"ok": True, "pilot": dict(pilot)}

    def accept(
        self,
        *,
        pilot_id: UUID,
        request: PilotAcceptRequest,
        actor: str,
    ) -> dict[str, Any]:
        actual_runbook_sha256 = p100_runbook_sha256()
        if request.runbook_sha256 != actual_runbook_sha256:
            raise AcceptancePilotError(
                "pilot_runbook_digest_mismatch",
                details={
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "expected_sha256": actual_runbook_sha256,
                },
            )
        readiness = self.readiness(pilot_id=pilot_id)
        if not readiness["ready_for_acceptance"]:
            raise AcceptancePilotError(
                "pilot_not_ready_for_acceptance",
                details={"blockers": readiness["blockers"]},
            )
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='accepted',
                       accepted_by=%s,
                       accepted_at=now(),
                       production_release_tag=%s,
                       release_tagged_by=%s,
                       release_tagged_at=now(),
                       runbook_path=%s,
                       runbook_sha256=%s
                   WHERE id=%s AND status IN ('running','blocked')
                   RETURNING *""",
                (
                    actor,
                    request.production_release_tag,
                    actor,
                    P100_RUNBOOK_RELATIVE_PATH,
                    actual_runbook_sha256,
                    pilot_id,
                ),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_acceptable")
            self._event(
                conn,
                pilot_id,
                None,
                "pilot_accepted",
                actor,
                {
                    "production_release_tag": request.production_release_tag,
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "runbook_sha256": actual_runbook_sha256,
                },
            )
        return {"ok": True, "pilot": dict(pilot)}

    def readiness(self, *, pilot_id: UUID) -> dict[str, Any]:
        """Return canonical readiness without inserting evidence or changing pilot state."""
        current_runbook_sha256 = p100_runbook_sha256()
        with self.database.connection() as conn:
            pilot = conn.execute(
                "SELECT * FROM football_brief.acceptance_pilots WHERE id=%s",
                (pilot_id,),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_found")
            items = conn.execute(
                """SELECT api.*,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.acceptance_pilot_items api
                   JOIN football_brief.brands b ON b.id=api.brand_id
                   WHERE api.pilot_id=%s ORDER BY b.slug,api.created_at,api.id""",
                (pilot_id,),
            ).fetchall()

            item_reports: list[dict[str, Any]] = []
            all_items_ready = bool(items)
            for item in items:
                checks = self._system_checks(conn, item)
                categories = [
                    {
                        "category": category.value,
                        "passed": bool(checks[category]["passed"]),
                        "subject_type": checks[category]["subject_type"],
                        "subject_id": checks[category]["subject_id"],
                        "subject_version": checks[category].get("subject_version"),
                    }
                    for category in CONTENT_CATEGORIES
                ]
                item_ready = all(entry["passed"] for entry in categories)
                all_items_ready = all_items_ready and item_ready
                item_reports.append(
                    {
                        "pilot_item_id": str(item["id"]),
                        "brand_id": str(item["brand_id"]),
                        "brand_slug": item["brand_slug"],
                        "portfolio_content_id": str(item["portfolio_content_id"]),
                        "content_version": int(item["content_version"]),
                        "production_mode": item["production_mode"],
                        "stored_status": item["status"],
                        "canonical_ready": item_ready,
                        "categories": categories,
                    }
                )

            operations = {
                EvidenceCategory.BACKUP_RESTORE.value: self._operation_readiness(
                    conn,
                    pilot_id=pilot_id,
                    category=EvidenceCategory.BACKUP_RESTORE,
                ),
                EvidenceCategory.WORKER_RESTART.value: self._operation_readiness(
                    conn,
                    pilot_id=pilot_id,
                    category=EvidenceCategory.WORKER_RESTART,
                ),
                EvidenceCategory.RUNBOOK_VALIDATION.value: self._operation_readiness(
                    conn,
                    pilot_id=pilot_id,
                    category=EvidenceCategory.RUNBOOK_VALIDATION,
                    runbook_sha256=current_runbook_sha256,
                ),
            }
            operations_ready = all(entry["passed"] for entry in operations.values())

            defects = conn.execute(
                """SELECT severity,status,count(*) AS count
                   FROM football_brief.acceptance_pilot_defects
                   WHERE pilot_id=%s GROUP BY severity,status""",
                (pilot_id,),
            ).fetchall()
            blocking_defect_count = sum(
                int(row["count"])
                for row in defects
                if row["severity"] in {"major", "critical"} and row["status"] == "open"
            )

            signoffs = conn.execute(
                """SELECT signoff_role,decision,operator_id,created_at
                   FROM football_brief.acceptance_pilot_signoffs
                   WHERE pilot_id=%s ORDER BY created_at,id""",
                (pilot_id,),
            ).fetchall()
            approved_roles = {
                row["signoff_role"] for row in signoffs if row["decision"] == "approved"
            }
            rejected_roles = sorted(
                row["signoff_role"] for row in signoffs if row["decision"] == "rejected"
            )

            live_required_count = int(
                conn.execute(
                    """SELECT count(*) AS count FROM football_brief.acceptance_pilot_items
                       WHERE pilot_id=%s AND live_delivery_evidence_required""",
                    (pilot_id,),
                ).fetchone()["count"]
            )
            qualifying_live_count = int(
                conn.execute(
                    """SELECT count(*) AS count
                       FROM football_brief.acceptance_live_delivery_evidence alde
                       JOIN football_brief.acceptance_pilot_items api ON api.id=alde.pilot_item_id
                       JOIN football_brief.final_releases fr ON fr.id=alde.final_release_id
                       WHERE alde.pilot_id=%s
                         AND api.live_delivery_evidence_required
                         AND alde.result_status IN ('submitted','published')
                         AND fr.status='approved'
                         AND fr.portfolio_content_id=api.portfolio_content_id
                         AND fr.content_version=api.content_version""",
                    (pilot_id,),
                ).fetchone()["count"]
            )

        brand_counts: dict[str, int] = {}
        modes_by_brand: dict[str, set[str]] = {}
        brand_ids = sorted({str(item["brand_id"]) for item in items})
        for item in items:
            slug = item["brand_slug"]
            brand_counts[slug] = brand_counts.get(slug, 0) + 1
            modes_by_brand.setdefault(slug, set()).add(item["production_mode"])
        scope_ready = (
            len(items) == 4
            and set(brand_counts) == REQUIRED_BRAND_SLUGS
            and all(brand_counts.get(slug) == 2 for slug in REQUIRED_BRAND_SLUGS)
            and all(
                modes_by_brand.get(slug) == {"local_only", "managed_render"}
                for slug in REQUIRED_BRAND_SLUGS
            )
        )
        editable = pilot["status"] in {"running", "blocked"}
        ready_for_signoff = (
            editable
            and scope_ready
            and all_items_ready
            and operations_ready
            and blocking_defect_count == 0
        )
        signoffs_ready = (
            approved_roles == REQUIRED_SIGNOFF_ROLES and not rejected_roles
        )
        live_ready = live_required_count >= 1 and qualifying_live_count >= 1
        ready_for_acceptance = ready_for_signoff and signoffs_ready and live_ready

        blockers: list[dict[str, Any]] = []
        if not editable:
            blockers.append({"code": "pilot_not_running", "status": pilot["status"]})
        if not scope_ready:
            blockers.append(
                {
                    "code": "pilot_scope_incomplete",
                    "item_count": len(items),
                    "brand_counts": brand_counts,
                    "modes_by_brand": {
                        key: sorted(value) for key, value in modes_by_brand.items()
                    },
                }
            )
        for report in item_reports:
            missing = [
                entry["category"] for entry in report["categories"] if not entry["passed"]
            ]
            if missing:
                blockers.append(
                    {
                        "code": "pilot_item_canonical_evidence_incomplete",
                        "pilot_item_id": report["pilot_item_id"],
                        "missing_categories": missing,
                    }
                )
        for category, entry in operations.items():
            if not entry["passed"]:
                blockers.append(
                    {"code": "pilot_operations_evidence_missing", "category": category}
                )
        if blocking_defect_count:
            blockers.append(
                {"code": "pilot_blocking_defects_open", "count": blocking_defect_count}
            )
        missing_signoffs = sorted(REQUIRED_SIGNOFF_ROLES - approved_roles)
        if missing_signoffs or rejected_roles:
            blockers.append(
                {
                    "code": "pilot_signoffs_incomplete",
                    "missing_roles": missing_signoffs,
                    "rejected_roles": rejected_roles,
                }
            )
        if not live_ready:
            blockers.append(
                {
                    "code": "pilot_live_result_missing",
                    "required_item_count": live_required_count,
                    "qualifying_result_count": qualifying_live_count,
                }
            )

        return {
            "ok": True,
            "pilot_id": str(pilot_id),
            "pilot_key": pilot["pilot_key"],
            "pilot_version": int(pilot["version"]),
            "pilot_status": pilot["status"],
            "brand_ids": brand_ids,
            "scope": {
                "passed": scope_ready,
                "item_count": len(items),
                "brand_counts": brand_counts,
                "modes_by_brand": {
                    key: sorted(value) for key, value in modes_by_brand.items()
                },
            },
            "items": item_reports,
            "operations": operations,
            "defects": {
                "blocking_open_count": blocking_defect_count,
                "counts": [dict(row) for row in defects],
            },
            "signoffs": {
                "approved_roles": sorted(approved_roles),
                "missing_roles": sorted(REQUIRED_SIGNOFF_ROLES - approved_roles),
                "rejected_roles": rejected_roles,
                "items": [dict(row) for row in signoffs],
            },
            "live_result": {
                "required_item_count": live_required_count,
                "qualifying_result_count": qualifying_live_count,
                "passed": live_ready,
            },
            "runbook": {
                "path": P100_RUNBOOK_RELATIVE_PATH,
                "sha256": current_runbook_sha256,
            },
            "ready_for_signoff": ready_for_signoff,
            "ready_for_acceptance": ready_for_acceptance,
            "blockers": blockers,
        }

    def _operation_readiness(
        self,
        conn: Any,
        *,
        pilot_id: UUID,
        category: EvidenceCategory,
        runbook_sha256: str | None = None,
    ) -> dict[str, Any]:
        if category is EvidenceCategory.BACKUP_RESTORE:
            row = conn.execute(
                """SELECT ape.id,ape.subject_id,ape.observed_at
                   FROM football_brief.acceptance_pilot_evidence ape
                   JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
                   JOIN football_brief.operations_restore_events ore ON ore.id::text=ape.subject_id
                   WHERE api.pilot_id=%s AND ape.category='backup_restore' AND ape.passed
                     AND ore.database_restored AND ore.artifacts_restored
                     AND ore.migration_head_verified AND ore.database_sha256_verified
                     AND ore.artifact_sha256_verified
                   ORDER BY ape.observed_at DESC,ape.id DESC LIMIT 1""",
                (pilot_id,),
            ).fetchone()
        elif category is EvidenceCategory.WORKER_RESTART:
            row = conn.execute(
                """SELECT ape.id,ape.subject_id,ape.observed_at
                   FROM football_brief.acceptance_pilot_evidence ape
                   JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
                   JOIN football_brief.operations_drill_runs odr ON odr.id::text=ape.subject_id
                   WHERE api.pilot_id=%s AND ape.category='worker_restart' AND ape.passed
                     AND odr.environment='staging' AND odr.drill_kind='worker_restart'
                     AND odr.status='passed'
                   ORDER BY ape.observed_at DESC,ape.id DESC LIMIT 1""",
                (pilot_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT ape.id,ape.subject_id,ape.observed_at
                   FROM football_brief.acceptance_pilot_evidence ape
                   JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
                   JOIN football_brief.operations_drill_runs odr ON odr.id::text=ape.subject_id
                   WHERE api.pilot_id=%s AND ape.category='runbook_validation' AND ape.passed
                     AND odr.environment='staging' AND odr.drill_kind='runbook_validation'
                     AND odr.status='passed'
                     AND odr.evidence->>'runbook_path'=%s
                     AND odr.evidence->>'runbook_sha256'=%s
                     AND odr.evidence->>'operator_profile'='non_developer'
                     AND odr.evidence->>'checklist_completed'='true'
                   ORDER BY ape.observed_at DESC,ape.id DESC LIMIT 1""",
                (pilot_id, P100_RUNBOOK_RELATIVE_PATH, runbook_sha256),
            ).fetchone()
        return {
            "passed": bool(row),
            "evidence_id": str(row["id"]) if row else None,
            "subject_id": row["subject_id"] if row else None,
            "observed_at": row["observed_at"] if row else None,
        }

    def _resolve_operations_evidence(
        self,
        conn: Any,
        request: OperationsEvidenceRequest,
    ) -> dict[str, Any]:
        if request.category is not EvidenceCategory.RUNBOOK_VALIDATION:
            return super()._resolve_operations_evidence(conn, request)
        try:
            subject_uuid = UUID(request.subject_id)
        except ValueError as exc:
            raise AcceptancePilotError("operations_subject_id_must_be_uuid") from exc
        runbook_sha256 = p100_runbook_sha256()
        row = conn.execute(
            """SELECT * FROM football_brief.operations_drill_runs
               WHERE id=%s
                 AND environment='staging'
                 AND drill_kind='runbook_validation'
                 AND status='passed'
                 AND evidence->>'runbook_path'=%s
                 AND evidence->>'runbook_sha256'=%s
                 AND evidence->>'operator_profile'='non_developer'
                 AND evidence->>'checklist_completed'='true'
                 AND nullif(btrim(evidence->>'completed_by'),'') IS NOT NULL""",
            (subject_uuid, P100_RUNBOOK_RELATIVE_PATH, runbook_sha256),
        ).fetchone()
        return self._result(row, request.subject_type, row)

    def _system_checks(self, conn: Any, context: Any) -> dict[EvidenceCategory, dict[str, Any]]:
        checks = super()._system_checks(conn, context)
        if checks[EvidenceCategory.SOURCE_EVIDENCE]["passed"]:
            checks[EvidenceCategory.SOURCE_EVIDENCE]["subject_id"] = checks[
                EvidenceCategory.SCRIPT_APPROVAL
            ]["subject_id"]
            checks[EvidenceCategory.SOURCE_EVIDENCE]["subject_version"] = checks[
                EvidenceCategory.SCRIPT_APPROVAL
            ]["subject_version"]
        if (
            checks[EvidenceCategory.RENDERER_LINEAGE]["passed"]
            and str(checks[EvidenceCategory.RENDERER_LINEAGE]["subject_id"]).startswith("aggregate:")
        ):
            checks[EvidenceCategory.RENDERER_LINEAGE]["subject_id"] = checks[
                EvidenceCategory.ROUTING_EXPLANATION
            ]["subject_id"]
            checks[EvidenceCategory.RENDERER_LINEAGE]["subject_version"] = checks[
                EvidenceCategory.ROUTING_EXPLANATION
            ]["subject_version"]
        return checks

    @staticmethod
    def _result(value: Any, subject_type: str, details: Any) -> dict[str, Any]:
        result = AcceptancePilotService._result(value, subject_type, details)
        normalized = result["details"]
        exact_fields = {
            "audio_mix_version": "mix_id",
            "production_spend_decision": "spend_decision_id",
            "shared_artifact_version": "output_artifact_version_id",
            "platform_delivery_request": "delivery_request_id",
        }
        exact_field = exact_fields.get(subject_type)
        if result["passed"] and exact_field and normalized.get(exact_field):
            result["subject_id"] = str(normalized[exact_field])
        if result["passed"] and str(result["subject_id"]).startswith("missing:"):
            result["subject_id"] = f"aggregate:{_digest(normalized)}"
        return result
