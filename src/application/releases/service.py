from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError, GenerationJobService
from src.application.releases.models import (
    AssemblyEnqueueRequest,
    AssemblyOutputRequest,
    FinalReleaseCreate,
    PlaybackReviewRequest,
    QaEvaluateRequest,
    ReleaseDecisionRequest,
    ReleaseInputApprovalRequest,
    RenderProfileRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class FinalReleaseError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _check(code: str, passed: bool, message: str, *, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "status": "pass" if passed else "fail",
        "severity": "info" if passed else "block",
        "message": message,
        "observed": observed,
        "expected": expected,
    }


class FinalReleaseService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.jobs = GenerationJobService(database)

    def create_profile(self, request: RenderProfileRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"release-profile:{request.profile_key}",))
            existing = conn.execute(
                "SELECT id FROM football_brief.platform_render_profiles WHERE profile_key=%s LIMIT 1",
                (request.profile_key,),
            ).fetchone()
            if existing:
                raise FinalReleaseError("render_profile_key_exists")
            row = self._insert_profile(conn, request=request, version=1, parent_id=None, actor=actor, status="draft")
        return {"ok": True, "profile": dict(row)}

    def activate_profile(self, *, profile_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                "SELECT * FROM football_brief.platform_render_profiles WHERE id=%s FOR UPDATE",
                (profile_id,),
            ).fetchone()
            if not row:
                raise FinalReleaseError("render_profile_not_found")
            if row["status"] == "active":
                return {"ok": True, "profile": dict(row), "already_active": True}
            if row["status"] != "draft":
                raise FinalReleaseError("render_profile_not_activatable")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"release-profile:{row['profile_key']}",))
            active = conn.execute(
                """SELECT id FROM football_brief.platform_render_profiles
                   WHERE profile_key=%s AND status='active' AND id<>%s FOR UPDATE""",
                (row["profile_key"], profile_id),
            ).fetchone()
            if active:
                raise FinalReleaseError("render_profile_active_version_exists")
            activated = conn.execute(
                """UPDATE football_brief.platform_render_profiles
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, profile_id),
            ).fetchone()
        return {"ok": True, "profile": dict(activated)}

    def revise_profile(
        self,
        *,
        profile_id: UUID,
        request: RenderProfileRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            source = conn.execute(
                "SELECT * FROM football_brief.platform_render_profiles WHERE id=%s FOR UPDATE",
                (profile_id,),
            ).fetchone()
            if not source:
                raise FinalReleaseError("render_profile_not_found")
            if source["status"] != "active" or source["profile_key"] != request.profile_key:
                raise FinalReleaseError("render_profile_revision_requires_active_matching_key")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"release-profile:{source['profile_key']}",))
            retired = conn.execute(
                """UPDATE football_brief.platform_render_profiles
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, profile_id),
            ).fetchone()
            replacement = self._insert_profile(
                conn,
                request=request,
                version=int(source["version"]) + 1,
                parent_id=profile_id,
                actor=actor,
                status="active",
            )
        return {"ok": True, "profile": dict(replacement), "retired_profile": dict(retired)}

    def list_profiles(self, *, include_retired: bool = False) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.platform_render_profiles
                   WHERE %s OR status<>'retired'
                   ORDER BY profile_key,version DESC""",
                (include_retired,),
            ).fetchall()
        return [dict(row) for row in rows]

    def decide_input(
        self,
        request: ReleaseInputApprovalRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        payload = {
            "artifact_version_id": str(request.artifact_version_id),
            "role": request.role.value,
            "decision": request.decision,
            "reviewer": actor,
            "rationale": request.rationale,
        }
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """INSERT INTO football_brief.final_release_input_approvals
                   (artifact_version_id,role,decision,reviewer_operator_id,rationale,evidence_hash)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.artifact_version_id,
                    request.role.value,
                    request.decision,
                    actor,
                    request.rationale.strip(),
                    _hash(payload),
                ),
            ).fetchone()
        return {"ok": True, "approval": dict(row)}

    def create_release(self, request: FinalReleaseCreate, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"final-release:{request.portfolio_content_id}:{request.content_version}",),
            )
            open_row = conn.execute(
                """SELECT id,status FROM football_brief.final_releases
                   WHERE portfolio_content_id=%s AND content_version=%s
                     AND status IN ('draft','assembly_queued','assembled','qa_complete','in_review')
                   FOR UPDATE""",
                (request.portfolio_content_id, request.content_version),
            ).fetchone()
            if open_row:
                raise FinalReleaseError(
                    "final_release_open_version_exists",
                    details={"release_id": str(open_row["id"]), "status": open_row["status"]},
                )
            latest = conn.execute(
                """SELECT * FROM football_brief.final_releases
                   WHERE portfolio_content_id=%s AND content_version=%s
                   ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (request.portfolio_content_id, request.content_version),
            ).fetchone()
            version = int(latest["version"]) + 1 if latest else 1
            parent_id = latest["id"] if latest else None
            snapshots = [self._approved_input_snapshot(conn, item) for item in request.inputs]
            input_document = [
                {
                    "artifact_version_id": str(item["artifact"]["id"]),
                    "role": item["request"].role.value,
                    "sequence_number": item["request"].sequence_number,
                    "required": item["request"].required,
                    "canonical_asset_id": str(item["asset"]["id"]),
                    "asset_sha256": item["asset"]["sha256"],
                    "approval_id": str(item["approval"]["id"]),
                    "metadata": item["request"].metadata,
                }
                for item in snapshots
            ]
            input_document.sort(key=lambda item: (item["role"], item["sequence_number"], item["artifact_version_id"]))
            input_hash = _hash(input_document)
            release = conn.execute(
                """INSERT INTO football_brief.final_releases
                   (portfolio_content_id,content_version,version,parent_release_id,render_profile_id,
                    routing_plan_id,status,input_hash,metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,'draft',%s,%s::jsonb,%s) RETURNING *""",
                (
                    request.portfolio_content_id,
                    request.content_version,
                    version,
                    parent_id,
                    request.render_profile_id,
                    request.routing_plan_id,
                    input_hash,
                    _json(request.metadata),
                    actor,
                ),
            ).fetchone()
            for item in snapshots:
                artifact_snapshot = {
                    key: item["artifact"].get(key)
                    for key in (
                        "id", "brand_id", "portfolio_content_id", "content_version", "artifact_key",
                        "artifact_kind", "version", "parent_version_id", "status", "original_asset_id",
                        "review_proxy_asset_id", "thumbnail_asset_id", "metadata", "created_at",
                    )
                }
                conn.execute(
                    """INSERT INTO football_brief.final_release_inputs
                       (release_id,artifact_version_id,approval_id,role,sequence_number,required,
                        canonical_asset_id,asset_sha256,artifact_snapshot,metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
                    (
                        release["id"],
                        item["artifact"]["id"],
                        item["approval"]["id"],
                        item["request"].role.value,
                        item["request"].sequence_number,
                        item["request"].required,
                        item["asset"]["id"],
                        item["asset"]["sha256"],
                        _json(artifact_snapshot),
                        _json(item["request"].metadata),
                    ),
                )
            self._event(conn, release_id=release["id"], event="created", actor=actor, from_lock=None, to_lock=1, details={"version": version, "input_hash": input_hash})
            if latest and latest["status"] == "approved":
                superseded = conn.execute(
                    """UPDATE football_brief.final_releases
                       SET status='superseded',superseded_at=now(),lock_version=lock_version+1
                       WHERE id=%s RETURNING *""",
                    (latest["id"],),
                ).fetchone()
                self._event(
                    conn,
                    release_id=latest["id"],
                    event="superseded",
                    actor=actor,
                    from_lock=int(latest["lock_version"]),
                    to_lock=int(superseded["lock_version"]),
                    details={"replacement_release_id": str(release["id"])},
                )
        return self.detail(release_id=release["id"])

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
                return {"ok": True, "release": dict(release), "job": self.jobs.detail(job_id=release["assembly_job_id"])["job"], "reused": True}
            if release["status"] != "draft":
                raise FinalReleaseError("final_release_not_ready_for_assembly", details={"status": release["status"]})
            self._require_current_inputs(conn, release_id)
            blockers = conn.execute(
                """SELECT count(*) AS count FROM football_brief.creator_revision_tasks
                   WHERE portfolio_content_id=%s AND blocker=true AND status IN ('open','in_progress')""",
                (release["portfolio_content_id"],),
            ).fetchone()["count"]
            if blockers:
                raise FinalReleaseError("final_release_has_open_blocking_revision_tasks", details={"count": int(blockers)})
            profile = conn.execute("SELECT * FROM football_brief.platform_render_profiles WHERE id=%s", (release["render_profile_id"],)).fetchone()
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
            enqueued = self.jobs.enqueue(job_request, actor=actor)
        except GenerationJobError as exc:
            raise FinalReleaseError("final_release_assembly_enqueue_failed", details={"job_error": exc.code}) from exc
        job = enqueued["job"]
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
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
            self._event(conn, release_id=release_id, event="assembly_queued", actor=actor, from_lock=int(current["lock_version"]), to_lock=int(updated["lock_version"]), details={"job_id": str(job["id"])})
        return {"ok": True, "release": dict(updated), "job": job, "reused": bool(enqueued.get("reused"))}

    def register_assembly_output(
        self,
        *,
        release_id: UUID,
        request: AssemblyOutputRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            release = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            if release["status"] == "assembled" and release["output_artifact_version_id"] == request.output_artifact_version_id:
                return {"ok": True, "release": dict(release), "reused": True}
            if release["status"] != "assembly_queued" or release["assembly_job_id"] != request.generation_job_id:
                raise FinalReleaseError("final_release_assembly_output_binding_conflict")
            job = conn.execute("SELECT * FROM football_brief.generation_jobs WHERE id=%s", (request.generation_job_id,)).fetchone()
            if not job or job["status"] != "succeeded":
                raise FinalReleaseError("final_release_assembly_job_not_succeeded")
            if str((job["output_payload"] or {}).get("shared_artifact_version_id")) != str(request.output_artifact_version_id):
                raise FinalReleaseError("final_release_output_not_declared_by_job")
            route_cost = Decimal("0")
            if release["routing_plan_id"]:
                route_cost = Decimal(str(conn.execute(
                    """SELECT COALESCE(sum(CASE WHEN status='reserved' THEN GREATEST(reserved_amount,actual_amount)
                                                 ELSE actual_amount END),0) AS amount
                       FROM football_brief.production_spend_reservations WHERE routing_plan_id=%s""",
                    (release["routing_plan_id"],),
                ).fetchone()["amount"]))
            total_cost = route_cost + Decimal(str(job["actual_cost_usd"]))
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status='assembled',output_artifact_version_id=%s,assembled_at=now(),
                       total_cost_usd=%s,lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (request.output_artifact_version_id, total_cost, release_id),
            ).fetchone()
            self._event(conn, release_id=release_id, event="assembly_completed", actor=actor, from_lock=int(release["lock_version"]), to_lock=int(updated["lock_version"]), details={"job_id": str(request.generation_job_id), "output_artifact_version_id": str(request.output_artifact_version_id), "total_cost_usd": str(total_cost)})
        return {"ok": True, "release": dict(updated), "reused": False}

    def evaluate_qa(
        self,
        *,
        release_id: UUID,
        request: QaEvaluateRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            release = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            if release["status"] != "assembled":
                raise FinalReleaseError("final_release_not_ready_for_qa", details={"status": release["status"]})
            profile = conn.execute("SELECT * FROM football_brief.platform_render_profiles WHERE id=%s", (release["render_profile_id"],)).fetchone()
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
                    _hash(report_document),
                    request.inspector_label,
                    actor,
                ),
            ).fetchone()
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status='qa_complete',qa_completed_at=now(),lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (release_id,),
            ).fetchone()
            self._event(conn, release_id=release_id, event="qa_recorded", actor=actor, from_lock=int(release["lock_version"]), to_lock=int(updated["lock_version"]), details={"qa_report_id": str(report["id"]), "outcome": outcome, "blocking_failures": blocking})
        return {"ok": outcome == "pass", "release": dict(updated), "qa_report": dict(report)}

    def submit_playback_review(self, *, release_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            release = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            if release["status"] != "qa_complete":
                raise FinalReleaseError("final_release_not_ready_for_playback_review")
            latest = conn.execute(
                """SELECT * FROM football_brief.final_release_qa_reports
                   WHERE release_id=%s ORDER BY created_at DESC,id DESC LIMIT 1""",
                (release_id,),
            ).fetchone()
            if not latest or latest["outcome"] != "pass":
                raise FinalReleaseError("final_release_blocking_qa_failures")
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status='in_review',submitted_by=%s,submitted_at=now(),lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (actor, release_id),
            ).fetchone()
            self._event(conn, release_id=release_id, event="submitted", actor=actor, from_lock=int(release["lock_version"]), to_lock=int(updated["lock_version"]), details={"qa_report_id": str(latest["id"])})
        return {"ok": True, "release": dict(updated)}

    def record_playback_review(
        self,
        *,
        release_id: UUID,
        request: PlaybackReviewRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            release = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            document = {
                "release_id": str(release_id),
                "release_lock_version": int(release["lock_version"]),
                "decision": request.decision.value,
                "checklist": request.checklist,
                "rationale": request.rationale,
                "reviewer": reviewer,
            }
            review = conn.execute(
                """INSERT INTO football_brief.final_release_playback_reviews
                   (release_id,decision,checklist,rationale,reviewer_operator_id,
                    release_lock_version,review_hash)
                   VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING *""",
                (
                    release_id,
                    request.decision.value,
                    _json(request.checklist),
                    request.rationale.strip(),
                    reviewer,
                    release["lock_version"],
                    _hash(document),
                ),
            ).fetchone()
            self._event(conn, release_id=release_id, event="playback_reviewed", actor=reviewer, from_lock=int(release["lock_version"]), to_lock=int(release["lock_version"]), details={"review_id": str(review["id"]), "decision": review["decision"]})
        return {"ok": True, "review": dict(review)}

    def decide_release(
        self,
        *,
        release_id: UUID,
        request: ReleaseDecisionRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            release = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE", (release_id,)).fetchone()
            if not release:
                raise FinalReleaseError("final_release_not_found")
            if release["status"] != "in_review" or int(release["lock_version"]) != request.expected_lock_version:
                raise FinalReleaseError("final_release_decision_conflict", details={"status": release["status"], "lock_version": int(release["lock_version"])})
            playback = conn.execute(
                """SELECT * FROM football_brief.final_release_playback_reviews
                   WHERE release_id=%s ORDER BY created_at DESC,id DESC LIMIT 1""",
                (release_id,),
            ).fetchone()
            if not playback or playback["decision"] != request.decision.value:
                raise FinalReleaseError("final_release_decision_requires_matching_playback_review")
            qa = conn.execute(
                """SELECT * FROM football_brief.final_release_qa_reports
                   WHERE release_id=%s ORDER BY created_at DESC,id DESC LIMIT 1""",
                (release_id,),
            ).fetchone()
            manifest = None
            manifest_hash = None
            approved_at = None
            if request.decision.value == "approved":
                manifest = self._release_manifest(conn, release, qa=qa, playback=playback, reviewer=reviewer, rationale=request.rationale)
                manifest_hash = _hash(manifest)
                approved_at = _utcnow()
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status=%s,release_manifest=%s::jsonb,manifest_hash=%s,
                       approved_by=%s,approved_at=%s,lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (
                    request.decision.value,
                    _json(manifest) if manifest is not None else None,
                    manifest_hash,
                    reviewer if approved_at else None,
                    approved_at,
                    release_id,
                ),
            ).fetchone()
            self._event(conn, release_id=release_id, event=request.decision.value, actor=reviewer, from_lock=int(release["lock_version"]), to_lock=int(updated["lock_version"]), details={"rationale": request.rationale, "manifest_hash": manifest_hash})
        return {"ok": True, "release": dict(updated)}

    def detail(self, *, release_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            release = self._release(conn, release_id)
            inputs = conn.execute(
                """SELECT fri.*,sav.artifact_key,sav.artifact_kind,sav.version AS artifact_version,
                          sav.status AS artifact_status
                   FROM football_brief.final_release_inputs fri
                   JOIN football_brief.shared_artifact_versions sav ON sav.id=fri.artifact_version_id
                   WHERE fri.release_id=%s ORDER BY fri.role,fri.sequence_number,fri.id""",
                (release_id,),
            ).fetchall()
            qa = conn.execute(
                "SELECT * FROM football_brief.final_release_qa_reports WHERE release_id=%s ORDER BY created_at,id",
                (release_id,),
            ).fetchall()
            reviews = conn.execute(
                "SELECT * FROM football_brief.final_release_playback_reviews WHERE release_id=%s ORDER BY created_at,id",
                (release_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT * FROM football_brief.final_release_events WHERE release_id=%s ORDER BY created_at,id",
                (release_id,),
            ).fetchall()
        return {"ok": True, "release": dict(release), "inputs": [dict(row) for row in inputs], "qa_reports": [dict(row) for row in qa], "playback_reviews": [dict(row) for row in reviews], "events": [dict(row) for row in events]}

    def list_releases(self, *, content_id: UUID | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise FinalReleaseError("invalid_release_list_limit")
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT fr.*,pc.title,mp.brand_id,b.slug AS brand_slug
                   FROM football_brief.final_releases fr
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE (%s::uuid IS NULL OR fr.portfolio_content_id=%s)
                   ORDER BY fr.created_at DESC,fr.version DESC LIMIT %s""",
                (content_id, content_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _insert_profile(self, conn: Any, *, request: RenderProfileRequest, version: int, parent_id: UUID | None, actor: str, status: str) -> Mapping[str, Any]:
        return conn.execute(
            """INSERT INTO football_brief.platform_render_profiles
               (profile_key,version,parent_profile_id,status,display_name,platform,width,height,fps,
                container,video_codec,audio_codec,video_bitrate_kbps,audio_bitrate_kbps,
                min_duration_seconds,max_duration_seconds,safe_area,captions_required,caption_format,
                watermark_policy,disclosure_required,target_loudness_lufs,loudness_tolerance_lu,
                max_true_peak_dbfs,max_av_sync_offset_ms,configuration,created_by,
                activated_by,activated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s::jsonb,%s,%s,CASE WHEN %s='active' THEN now() END)
               RETURNING *""",
            (
                request.profile_key, version, parent_id, status, request.display_name, request.platform,
                request.width, request.height, request.fps, request.container, request.video_codec,
                request.audio_codec, request.video_bitrate_kbps, request.audio_bitrate_kbps,
                request.min_duration_seconds, request.max_duration_seconds, _json(request.safe_area),
                request.captions_required, request.caption_format, request.watermark_policy,
                request.disclosure_required, request.target_loudness_lufs, request.loudness_tolerance_lu,
                request.max_true_peak_dbfs, request.max_av_sync_offset_ms, _json(request.configuration),
                actor, actor if status == "active" else None, status,
            ),
        ).fetchone()

    def _approved_input_snapshot(self, conn: Any, request: Any) -> dict[str, Any]:
        artifact = conn.execute(
            "SELECT * FROM football_brief.shared_artifact_versions WHERE id=%s FOR SHARE",
            (request.artifact_version_id,),
        ).fetchone()
        if not artifact:
            raise FinalReleaseError("release_input_artifact_not_found")
        approval = conn.execute(
            """SELECT * FROM football_brief.final_release_input_approvals
               WHERE artifact_version_id=%s AND role=%s
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (request.artifact_version_id, request.role.value),
        ).fetchone()
        if artifact["status"] != "current" or not approval or approval["decision"] != "approved":
            raise FinalReleaseError("release_input_not_current_and_approved", details={"artifact_version_id": str(request.artifact_version_id), "role": request.role.value})
        asset = conn.execute("SELECT * FROM football_brief.assets WHERE id=%s", (artifact["original_asset_id"],)).fetchone()
        if not asset or asset["lifecycle_status"] in {"deleted", "expired", "rejected"}:
            raise FinalReleaseError("release_input_canonical_asset_unavailable")
        return {"request": request, "artifact": dict(artifact), "approval": dict(approval), "asset": dict(asset)}

    def _require_current_inputs(self, conn: Any, release_id: UUID) -> None:
        invalid = conn.execute(
            """SELECT fri.id,fri.role,fri.artifact_version_id,sav.status,a.sha256,fri.asset_sha256,
                      latest.decision
               FROM football_brief.final_release_inputs fri
               JOIN football_brief.shared_artifact_versions sav ON sav.id=fri.artifact_version_id
               JOIN football_brief.assets a ON a.id=fri.canonical_asset_id
               LEFT JOIN LATERAL (
                   SELECT decision FROM football_brief.final_release_input_approvals fra
                   WHERE fra.artifact_version_id=fri.artifact_version_id AND fra.role=fri.role
                   ORDER BY created_at DESC,id DESC LIMIT 1
               ) latest ON true
               WHERE fri.release_id=%s AND fri.required
                 AND (sav.status<>'current' OR a.sha256<>fri.asset_sha256 OR latest.decision IS DISTINCT FROM 'approved')""",
            (release_id,),
        ).fetchall()
        if invalid:
            raise FinalReleaseError("final_release_inputs_superseded_or_unapproved", details={"inputs": [dict(row) for row in invalid]})

    def _qa_checks(self, profile: Mapping[str, Any], output: Mapping[str, Any], request: QaEvaluateRequest) -> list[dict[str, Any]]:
        i = request.inspection
        checks = [
            _check("FILE_INTEGRITY", i.valid_container and i.file_sha256 == output["output_hash"], "Output container and checksum must be valid", observed={"valid_container": i.valid_container, "sha256": i.file_sha256}, expected=output["output_hash"]),
            _check("DIMENSIONS", i.width == profile["width"] and i.height == profile["height"], "Output dimensions must match the platform profile", observed=[i.width, i.height], expected=[profile["width"], profile["height"]]),
            _check("FRAME_RATE", i.fps is not None and abs(Decimal(str(i.fps)) - Decimal(str(profile["fps"]))) <= Decimal("0.25"), "Frame rate must match the platform profile", observed=i.fps, expected=profile["fps"]),
            _check("DURATION", i.duration_seconds is not None and Decimal(str(profile["min_duration_seconds"])) <= Decimal(str(i.duration_seconds)) <= Decimal(str(profile["max_duration_seconds"])), "Duration must be within the platform range", observed=i.duration_seconds, expected=[profile["min_duration_seconds"], profile["max_duration_seconds"]]),
            _check("CONTAINER", (i.container or "").lower() == str(profile["container"]).lower(), "Container must match the platform profile", observed=i.container, expected=profile["container"]),
            _check("VIDEO_CODEC", (i.video_codec or "").lower() == str(profile["video_codec"]).lower(), "Video codec must match the platform profile", observed=i.video_codec, expected=profile["video_codec"]),
            _check("AUDIO_CODEC", (i.audio_codec or "").lower() == str(profile["audio_codec"]).lower(), "Audio codec must match the platform profile", observed=i.audio_codec, expected=profile["audio_codec"]),
            _check("VIDEO_BITRATE", i.video_bitrate_kbps is not None and i.video_bitrate_kbps >= int(profile["video_bitrate_kbps"]), "Video bitrate must meet the platform minimum", observed=i.video_bitrate_kbps, expected=profile["video_bitrate_kbps"]),
            _check("AUDIO_BITRATE", i.audio_bitrate_kbps is not None and i.audio_bitrate_kbps >= int(profile["audio_bitrate_kbps"]), "Audio bitrate must meet the platform minimum", observed=i.audio_bitrate_kbps, expected=profile["audio_bitrate_kbps"]),
            _check("AUDIO_TRACK", i.has_audio is True, "Final output requires an audio track", observed=i.has_audio, expected=True),
            _check("MISSING_FRAMES", i.missing_frame_count == 0, "No missing frames are allowed", observed=i.missing_frame_count, expected=0),
            _check("FROZEN_SEGMENTS", i.frozen_segment_count == 0, "No unintended frozen segments are allowed", observed=i.frozen_segment_count, expected=0),
            _check("BLACK_FRAMES", i.black_frame_count == 0, "No unintended black frames are allowed", observed=i.black_frame_count, expected=0),
            _check("DUPLICATE_SHOTS", not i.duplicate_shot_pairs, "No duplicate shot pairs are allowed", observed=i.duplicate_shot_pairs, expected=[]),
            _check("CAPTION_TIMING", i.caption_timing_violation_count == 0, "Caption timings must stay within the media timeline", observed=i.caption_timing_violation_count, expected=0),
            _check("CAPTION_CLIPPING", not i.caption_clipping_detected, "Captions must not be clipped", observed=i.caption_clipping_detected, expected=False),
            _check("SAFE_AREA", not i.safe_area_violation, "Captions and branding must remain inside the safe area", observed=i.safe_area_violation, expected=False),
            _check("AV_SYNC", i.av_sync_offset_ms is not None and abs(i.av_sync_offset_ms) <= int(profile["max_av_sync_offset_ms"]), "Audio/video sync must remain inside tolerance", observed=i.av_sync_offset_ms, expected=profile["max_av_sync_offset_ms"]),
            _check("LOUDNESS", i.integrated_loudness_lufs is not None and abs(Decimal(str(i.integrated_loudness_lufs)) - Decimal(str(profile["target_loudness_lufs"]))) <= Decimal(str(profile["loudness_tolerance_lu"])), "Integrated loudness must match the profile", observed=i.integrated_loudness_lufs, expected={"target": profile["target_loudness_lufs"], "tolerance": profile["loudness_tolerance_lu"]}),
            _check("TRUE_PEAK", i.true_peak_dbfs is not None and Decimal(str(i.true_peak_dbfs)) <= Decimal(str(profile["max_true_peak_dbfs"])), "True peak must remain below the profile maximum", observed=i.true_peak_dbfs, expected=profile["max_true_peak_dbfs"]),
            _check("AUDIO_CLIPPING", not i.audio_clipping_detected, "Audio clipping is not allowed", observed=i.audio_clipping_detected, expected=False),
        ]
        if profile["captions_required"]:
            checks.append(_check("CAPTIONS_PRESENT", i.captions_present is True, "Captions are required", observed=i.captions_present, expected=True))
            if i.captions_present:
                required_format = str(profile["caption_format"])
                checks.append(_check("CAPTION_FORMAT", required_format == "either" or i.caption_format == required_format, "Caption format must match the profile", observed=i.caption_format, expected=required_format))
        if profile["watermark_policy"] == "forbidden":
            checks.append(_check("WATERMARK_FORBIDDEN", i.watermark_present is False, "Publish output must not contain a preview watermark", observed=i.watermark_present, expected=False))
        elif profile["watermark_policy"] == "required":
            checks.append(_check("WATERMARK_REQUIRED", i.watermark_present is True, "The platform profile requires a watermark", observed=i.watermark_present, expected=True))
        if profile["disclosure_required"]:
            checks.append(_check("DISCLOSURE_PRESENT", i.disclosure_present is True, "Required disclosure must be present", observed=i.disclosure_present, expected=True))
        return checks

    def _release_manifest(self, conn: Any, release: Mapping[str, Any], *, qa: Mapping[str, Any], playback: Mapping[str, Any], reviewer: str, rationale: str) -> dict[str, Any]:
        profile = conn.execute("SELECT * FROM football_brief.platform_render_profiles WHERE id=%s", (release["render_profile_id"],)).fetchone()
        inputs = conn.execute(
            """SELECT role,sequence_number,required,artifact_version_id,canonical_asset_id,
                      asset_sha256,approval_id,artifact_snapshot,metadata
               FROM football_brief.final_release_inputs WHERE release_id=%s
               ORDER BY role,sequence_number,id""",
            (release["id"],),
        ).fetchall()
        output = conn.execute(
            """SELECT sav.id,sav.artifact_key,sav.artifact_kind,sav.version,sav.status,
                      sav.original_asset_id,a.sha256,a.size_bytes,a.mime_type
               FROM football_brief.shared_artifact_versions sav
               JOIN football_brief.assets a ON a.id=sav.original_asset_id
               WHERE sav.id=%s""",
            (release["output_artifact_version_id"],),
        ).fetchone()
        job = conn.execute("SELECT * FROM football_brief.generation_jobs WHERE id=%s", (release["assembly_job_id"],)).fetchone()
        return {
            "schema": "final-release-manifest-v1",
            "release": {
                "id": str(release["id"]),
                "portfolio_content_id": str(release["portfolio_content_id"]),
                "content_version": int(release["content_version"]),
                "version": int(release["version"]),
                "parent_release_id": str(release["parent_release_id"]) if release["parent_release_id"] else None,
                "input_hash": release["input_hash"],
                "total_cost_usd": str(release["total_cost_usd"]),
            },
            "profile": self._profile_snapshot(profile),
            "inputs": [dict(row) for row in inputs],
            "assembly": {
                "generation_job_id": str(job["id"]),
                "provider": job["provider"],
                "model_id": job["model_id"],
                "input_fingerprint": job["input_fingerprint"],
                "output_fingerprint": job["output_fingerprint"],
                "attempt_count": int(job["attempt_count"]),
                "actual_cost_usd": str(job["actual_cost_usd"]),
            },
            "output": dict(output),
            "qa": {
                "report_id": str(qa["id"]),
                "outcome": qa["outcome"],
                "report_hash": qa["report_hash"],
                "checks": qa["checks"],
                "blocking_failures": qa["blocking_failures"],
            },
            "playback_review": {
                "review_id": str(playback["id"]),
                "decision": playback["decision"],
                "review_hash": playback["review_hash"],
                "checklist": playback["checklist"],
                "reviewer": playback["reviewer_operator_id"],
            },
            "approval": {
                "reviewer": reviewer,
                "approved_at": _utcnow().isoformat(),
                "rationale": rationale,
            },
        }

    @staticmethod
    def _profile_snapshot(profile: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: profile[key]
            for key in (
                "id", "profile_key", "version", "platform", "width", "height", "fps",
                "container", "video_codec", "audio_codec", "video_bitrate_kbps",
                "audio_bitrate_kbps", "min_duration_seconds", "max_duration_seconds",
                "safe_area", "captions_required", "caption_format", "watermark_policy",
                "disclosure_required", "target_loudness_lufs", "loudness_tolerance_lu",
                "max_true_peak_dbfs", "max_av_sync_offset_ms", "configuration",
            )
        }

    @staticmethod
    def _release(conn: Any, release_id: UUID) -> Mapping[str, Any]:
        row = conn.execute("SELECT * FROM football_brief.final_releases WHERE id=%s", (release_id,)).fetchone()
        if not row:
            raise FinalReleaseError("final_release_not_found")
        return row

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        row = conn.execute("SELECT active FROM football_brief.operator_users WHERE operator_id=%s", (actor,)).fetchone()
        if not row or not bool(row["active"]):
            raise FinalReleaseError("operator_inactive_or_missing")

    @staticmethod
    def _event(conn: Any, *, release_id: UUID, event: str, actor: str, from_lock: int | None, to_lock: int, details: dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO football_brief.final_release_events
               (release_id,event,actor,from_lock_version,to_lock_version,details)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
            (release_id, event, actor, from_lock, to_lock, _json(details)),
        )
