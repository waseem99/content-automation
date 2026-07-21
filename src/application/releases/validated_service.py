from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.releases.models import AssemblyEnqueueRequest, QaEvaluateRequest
from src.application.releases.service import (
    FinalReleaseError,
    FinalReleaseService,
    _hash,
    _json,
)


class ValidatedFinalReleaseService(FinalReleaseService):
    """Final release service bound to P87, P94, and retry-safe QA contracts."""

    def enqueue_assembly(
        self,
        *,
        release_id: UUID,
        request: AssemblyEnqueueRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            release = self._release(conn, release_id)
            if release["status"] == "assembly_queued" and release["assembly_job_id"]:
                return {
                    "ok": True,
                    "release": dict(release),
                    "job": self.jobs.detail(job_id=release["assembly_job_id"])["job"],
                    "reused": True,
                }
            if release["status"] != "draft":
                raise FinalReleaseError(
                    "final_release_not_ready_for_assembly",
                    details={"status": release["status"]},
                )
            self._require_current_inputs(conn, release_id)
            self._require_routing_ready(conn, release)
            blockers = conn.execute(
                """SELECT count(*) AS count FROM football_brief.creator_revision_tasks
                   WHERE portfolio_content_id=%s AND blocker=true AND status IN ('open','in_progress')""",
                (release["portfolio_content_id"],),
            ).fetchone()["count"]
            if blockers:
                raise FinalReleaseError(
                    "final_release_has_open_blocking_revision_tasks",
                    details={"count": int(blockers)},
                )
            profile = conn.execute(
                "SELECT * FROM football_brief.platform_render_profiles WHERE id=%s",
                (release["render_profile_id"],),
            ).fetchone()
            inputs = conn.execute(
                """SELECT role,sequence_number,artifact_version_id,canonical_asset_id,asset_sha256,
                          artifact_snapshot,metadata
                   FROM football_brief.final_release_inputs WHERE release_id=%s
                   ORDER BY role,sequence_number,id""",
                (release_id,),
            ).fetchall()

        job_request = GenerationJobEnqueue(
            portfolio_content_id=release["portfolio_content_id"],
            content_version=int(release["content_version"]),
            job_type=GenerationJobType.ASSEMBLY,
            provider="local-assembly",
            model_id="deterministic-release-assembler-v1",
            preferred_worker_id=request.preferred_worker_id,
            priority=request.priority,
            idempotency_key=f"final-release:{release_id}:assembly:v{release['version']}",
            input_payload={
                "final_release_id": str(release_id),
                "input_hash": release["input_hash"],
                "profile": self._profile_snapshot(profile),
                "inputs": [dict(row) for row in inputs],
            },
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
        )
        try:
            job = self.jobs.enqueue(job_request, actor=actor)
        except GenerationJobError as exc:
            raise FinalReleaseError(
                "final_release_assembly_enqueue_failed",
                details={"job_error": exc.code},
            ) from exc

        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = conn.execute(
                "SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE",
                (release_id,),
            ).fetchone()
            if current["status"] == "assembly_queued" and current["assembly_job_id"] == job["id"]:
                return {"ok": True, "release": dict(current), "job": job, "reused": True}
            if current["status"] != "draft":
                raise FinalReleaseError("final_release_assembly_binding_conflict")
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status='assembly_queued',assembly_job_id=%s,assembly_queued_at=now(),
                       lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (job["id"], release_id),
            ).fetchone()
            self._event(
                conn,
                release_id=release_id,
                event="assembly_queued",
                actor=actor,
                from_lock=int(current["lock_version"]),
                to_lock=int(updated["lock_version"]),
                details={"job_id": str(job["id"])},
            )
        return {
            "ok": True,
            "release": dict(updated),
            "job": job,
            "reused": bool(job.get("reused")),
        }

    def evaluate_qa(
        self,
        *,
        release_id: UUID,
        request: QaEvaluateRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            release = conn.execute(
                "SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE",
                (release_id,),
            ).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            if release["status"] != "assembled":
                raise FinalReleaseError(
                    "final_release_not_ready_for_qa",
                    details={"status": release["status"]},
                )
            profile = conn.execute(
                "SELECT * FROM football_brief.platform_render_profiles WHERE id=%s",
                (release["render_profile_id"],),
            ).fetchone()
            output = conn.execute(
                """SELECT sav.*,a.sha256 AS output_hash,a.size_bytes,a.mime_type
                   FROM football_brief.shared_artifact_versions sav
                   JOIN football_brief.assets a ON a.id=sav.original_asset_id
                   WHERE sav.id=%s""",
                (release["output_artifact_version_id"],),
            ).fetchone()
            checks = self._qa_checks(profile, output, request)
            blocking = [item["code"] for item in checks if item["status"] == "fail"]
            outcome = "block" if blocking else "pass"
            inspection = request.inspection.model_dump(mode="json")
            report_document = {
                "release_id": str(release_id),
                "output_artifact_version_id": str(output["id"]),
                "profile_id": str(profile["id"]),
                "input_hash": release["input_hash"],
                "output_hash": output["output_hash"],
                "outcome": outcome,
                "checks": checks,
                "inspection": inspection,
                "inspector_label": request.inspector_label,
            }
            report_hash = _hash(report_document)
            report = conn.execute(
                """SELECT * FROM football_brief.final_release_qa_reports
                   WHERE report_hash=%s""",
                (report_hash,),
            ).fetchone()
            reused = report is not None
            if report is None:
                report = conn.execute(
                    """INSERT INTO football_brief.final_release_qa_reports
                       (release_id,output_artifact_version_id,profile_id,outcome,checks,blocking_failures,
                        inspection,input_hash,output_hash,report_hash,inspector_label,created_by)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                       RETURNING *""",
                    (
                        release_id,
                        output["id"],
                        profile["id"],
                        outcome,
                        _json(checks),
                        _json(blocking),
                        _json(inspection),
                        release["input_hash"],
                        output["output_hash"],
                        report_hash,
                        request.inspector_label,
                        actor,
                    ),
                ).fetchone()

            updated = release
            to_lock = int(release["lock_version"])
            if outcome == "pass":
                updated = conn.execute(
                    """UPDATE football_brief.final_releases
                       SET status='qa_complete',qa_completed_at=now(),lock_version=lock_version+1
                       WHERE id=%s RETURNING *""",
                    (release_id,),
                ).fetchone()
                to_lock = int(updated["lock_version"])
            self._event(
                conn,
                release_id=release_id,
                event="qa_recorded",
                actor=actor,
                from_lock=int(release["lock_version"]),
                to_lock=to_lock,
                details={
                    "qa_report_id": str(report["id"]),
                    "outcome": outcome,
                    "blocking_failures": blocking,
                    "reused": reused,
                },
            )
        return {
            "ok": outcome == "pass",
            "release": dict(updated),
            "qa_report": dict(report),
            "reused": reused,
        }

    @staticmethod
    def _require_routing_ready(conn: Any, release: Any) -> None:
        if release["routing_plan_id"] is None:
            return
        route_count = int(
            conn.execute(
                "SELECT count(*) AS count FROM football_brief.shot_routing_items WHERE routing_plan_id=%s",
                (release["routing_plan_id"],),
            ).fetchone()["count"]
        )
        mapped_count = int(
            conn.execute(
                """SELECT count(DISTINCT (metadata->>'routing_item_id')::uuid) AS count
                   FROM football_brief.final_release_inputs
                   WHERE release_id=%s AND role='visual_shot' AND metadata ? 'routing_item_id'""",
                (release["id"],),
            ).fetchone()["count"]
        )
        if route_count == 0 or mapped_count != route_count:
            raise FinalReleaseError(
                "final_release_routing_inputs_incomplete",
                details={"routing_item_count": route_count, "mapped_visual_count": mapped_count},
            )
        invalid_managed = conn.execute(
            """SELECT sri.id,sri.visual_shot_id,psr.status AS reservation_status,
                      gj.id AS generation_job_id,gj.status AS generation_job_status
               FROM football_brief.shot_routing_items sri
               LEFT JOIN football_brief.production_spend_reservations psr
                 ON psr.routing_item_id=sri.id
               LEFT JOIN football_brief.generation_jobs gj
                 ON gj.id=psr.generation_job_id
               WHERE sri.routing_plan_id=%s AND sri.route='managed_render'
                 AND (
                     psr.id IS NULL OR psr.status<>'reconciled'
                     OR gj.id IS NULL OR gj.status<>'succeeded'
                 )
               ORDER BY sri.id""",
            (release["routing_plan_id"],),
        ).fetchall()
        if invalid_managed:
            raise FinalReleaseError(
                "final_release_managed_routes_not_settled",
                details={"items": [dict(row) for row in invalid_managed]},
            )
