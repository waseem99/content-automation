from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from src.application.video_pilot.models import (
    DistributionScope,
    ModelUsePreflightRequest,
    PilotAttemptCompleteRequest,
    PilotAttemptCreateRequest,
    PilotAttemptReviewRequest,
    PilotAttemptStatus,
    PilotCaseCreateRequest,
    PilotItemCreateRequest,
    PilotReviewDecision,
    PilotRunCreateRequest,
    PilotRunStartRequest,
)
from src.application.video_pilot.policy import evaluate_model_policy
from src.application.video_pilot.reporting import compile_pilot_report
from src.application.video_pilot.validation import PilotSnapshotValidationError, assert_snapshot_safe
from src.infrastructure.database.connection import Database


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class VideoPilotError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


class VideoPilotService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def model_use_matrix(self) -> dict[str, Any]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.video_model_use_policies
                   WHERE status='active' ORDER BY provider_key,model_key,version DESC"""
            ).fetchall()
        return {"ok": True, "kind": "video_model_use_matrix", "policies": [dict(row) for row in rows]}

    def model_use_preflight(self, request: ModelUsePreflightRequest) -> dict[str, Any]:
        with self.database.connection() as conn:
            policy = self._active_policy(conn, request.provider_key, request.model_key)
        return evaluate_model_policy(policy, request)

    def create_run(self, request: PilotRunCreateRequest, *, actor: str) -> dict[str, Any]:
        self._validate_snapshots(
            hardware_snapshot=request.hardware_snapshot,
            software_snapshot=request.software_snapshot,
            baseline_assumptions=request.baseline_assumptions,
        )
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"video-pilot:{request.run_key}",))
            existing = conn.execute(
                "SELECT id FROM football_brief.video_pilot_runs WHERE run_key=%s",
                (request.run_key,),
            ).fetchone()
            if existing:
                raise VideoPilotError("pilot_run_key_exists", details={"pilot_run_id": str(existing["id"])})
            run = conn.execute(
                """INSERT INTO football_brief.video_pilot_runs
                   (run_key,title,target_videos,target_attempts,hardware_snapshot,software_snapshot,
                    baseline_assumptions,created_by)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s) RETURNING *""",
                (
                    request.run_key,
                    request.title.strip(),
                    request.target_videos,
                    request.target_attempts,
                    _json(request.hardware_snapshot),
                    _json(request.software_snapshot),
                    _json(request.baseline_assumptions),
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "kind": "video_pilot_run_created", "run": dict(run)}

    def start_run(self, run_id: UUID, request: PilotRunStartRequest, *, actor: str) -> dict[str, Any]:
        hardware = request.hardware_snapshot or {}
        software = request.software_snapshot or {}
        self._validate_snapshots(hardware_snapshot=hardware, software_snapshot=software)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            run = conn.execute(
                "SELECT * FROM football_brief.video_pilot_runs WHERE id=%s FOR UPDATE",
                (run_id,),
            ).fetchone()
            if not run:
                raise VideoPilotError("pilot_run_not_found")
            if run["status"] == "running":
                return {"ok": True, "kind": "video_pilot_run_started", "reused": True, "run": dict(run)}
            if run["status"] != "planned":
                raise VideoPilotError("pilot_run_not_startable", details={"status": run["status"]})
            updated = conn.execute(
                """UPDATE football_brief.video_pilot_runs
                   SET status='running',started_by=%s,started_at=now(),
                       hardware_snapshot=hardware_snapshot || %s::jsonb,
                       software_snapshot=software_snapshot || %s::jsonb
                   WHERE id=%s RETURNING *""",
                (actor, _json(hardware), _json(software), run_id),
            ).fetchone()
        return {"ok": True, "kind": "video_pilot_run_started", "reused": False, "run": dict(updated)}

    def create_item(self, run_id: UUID, request: PilotItemCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            run = self._editable_run(conn, run_id)
            if request.portfolio_content_id and not conn.execute(
                "SELECT id FROM football_brief.portfolio_content WHERE id=%s",
                (request.portfolio_content_id,),
            ).fetchone():
                raise VideoPilotError("portfolio_content_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.video_pilot_items WHERE pilot_run_id=%s AND item_key=%s",
                (run["id"], request.item_key),
            ).fetchone()
            if existing:
                raise VideoPilotError("pilot_item_key_exists", details={"pilot_item_id": str(existing["id"])})
            item = conn.execute(
                """INSERT INTO football_brief.video_pilot_items
                   (pilot_run_id,item_key,title,portfolio_content_id,target_duration_seconds,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,'planned',%s) RETURNING *""",
                (
                    run_id,
                    request.item_key,
                    request.title.strip(),
                    request.portfolio_content_id,
                    request.target_duration_seconds,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "kind": "video_pilot_item_created", "item": dict(item)}

    def create_case(self, run_id: UUID, request: PilotCaseCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            self._editable_run(conn, run_id)
            item = conn.execute(
                "SELECT id,status FROM football_brief.video_pilot_items WHERE id=%s AND pilot_run_id=%s FOR UPDATE",
                (request.pilot_item_id, run_id),
            ).fetchone()
            if not item:
                raise VideoPilotError("pilot_item_not_found")
            if item["status"] in {"completed", "cancelled"}:
                raise VideoPilotError("pilot_item_not_editable", details={"status": item["status"]})
            if request.input_asset_id and not conn.execute(
                "SELECT id FROM football_brief.assets WHERE id=%s", (request.input_asset_id,)
            ).fetchone():
                raise VideoPilotError("pilot_input_asset_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.video_pilot_cases WHERE pilot_run_id=%s AND case_key=%s",
                (run_id, request.case_key),
            ).fetchone()
            if existing:
                raise VideoPilotError("pilot_case_key_exists", details={"pilot_case_id": str(existing["id"])})
            case = conn.execute(
                """INSERT INTO football_brief.video_pilot_cases
                   (pilot_run_id,pilot_item_id,case_key,title,shot_class,difficulty,distribution_scope,
                    release_territories,target_duration_seconds,prompt,negative_prompt,input_asset_id,
                    required_model_keys,acceptance_criteria,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::text[],%s,%s,%s,%s,%s::text[],%s::jsonb,'ready',%s)
                   RETURNING *""",
                (
                    run_id,
                    request.pilot_item_id,
                    request.case_key,
                    request.title.strip(),
                    request.shot_class.value,
                    request.difficulty.value,
                    request.distribution_scope.value,
                    list(request.release_territories),
                    request.target_duration_seconds,
                    request.prompt.strip(),
                    request.negative_prompt.strip() if request.negative_prompt else None,
                    request.input_asset_id,
                    list(request.required_model_keys),
                    _json(request.acceptance_criteria),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE football_brief.video_pilot_items SET status='production' WHERE id=%s AND status='planned'",
                (request.pilot_item_id,),
            )
        return {"ok": True, "kind": "video_pilot_case_created", "case": dict(case)}

    def create_attempt(self, case_id: UUID, request: PilotAttemptCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            case = conn.execute(
                """SELECT c.*,r.status AS run_status,i.status AS item_status
                   FROM football_brief.video_pilot_cases c
                   JOIN football_brief.video_pilot_runs r ON r.id=c.pilot_run_id
                   JOIN football_brief.video_pilot_items i ON i.id=c.pilot_item_id
                   WHERE c.id=%s FOR UPDATE OF c,r,i""",
                (case_id,),
            ).fetchone()
            if not case:
                raise VideoPilotError("pilot_case_not_found")
            if case["run_status"] != "running":
                raise VideoPilotError("pilot_run_not_running", details={"status": case["run_status"]})
            if case["status"] in {"completed", "cancelled"} or case["item_status"] in {"completed", "cancelled"}:
                raise VideoPilotError("pilot_case_not_attemptable")

            policy = self._active_policy(conn, request.provider_key, request.model_key)
            preflight = evaluate_model_policy(
                policy,
                ModelUsePreflightRequest(
                    provider_key=request.provider_key,
                    model_key=request.model_key,
                    distribution_scope=DistributionScope(str(case["distribution_scope"])),
                    release_territories=tuple(case["release_territories"] or ()),
                ),
            )
            if not preflight["accepted"]:
                raise VideoPilotError(
                    "video_model_use_not_allowed",
                    details={"policy_id": str(policy["id"]), "rejection_reasons": preflight["rejection_reasons"]},
                )
            self._validate_attempt_bindings(conn, request)
            next_number = int(
                conn.execute(
                    "SELECT COALESCE(max(attempt_number),0)+1 AS value FROM football_brief.video_pilot_attempts WHERE pilot_case_id=%s",
                    (case_id,),
                ).fetchone()["value"]
            )
            attempt = conn.execute(
                """INSERT INTO football_brief.video_pilot_attempts
                   (pilot_case_id,attempt_number,model_policy_id,renderer_catalogue_entry_id,
                    generation_job_id,workflow_key,workflow_sha256,checkpoint_sha256,seed,width,height,
                    fps,frame_count,inference_steps,status,started_at,metrics,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    case_id,
                    next_number,
                    policy["id"],
                    request.renderer_catalogue_entry_id,
                    request.generation_job_id,
                    request.workflow_key,
                    request.workflow_sha256,
                    request.checkpoint_sha256,
                    request.seed,
                    request.width,
                    request.height,
                    request.fps,
                    request.frame_count,
                    request.inference_steps,
                    request.started_at,
                    _json({"model_use_preflight": preflight}),
                    actor,
                ),
            ).fetchone()
            conn.execute("UPDATE football_brief.video_pilot_cases SET status='running' WHERE id=%s", (case_id,))
        return {"ok": True, "kind": "video_pilot_attempt_created", "attempt": dict(attempt), "preflight": preflight}

    def complete_attempt(self, attempt_id: UUID, request: PilotAttemptCompleteRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = conn.execute(
                "SELECT * FROM football_brief.video_pilot_attempts WHERE id=%s FOR UPDATE",
                (attempt_id,),
            ).fetchone()
            if not current:
                raise VideoPilotError("pilot_attempt_not_found")
            if current["status"] != "running":
                raise VideoPilotError("pilot_attempt_already_terminal", details={"status": current["status"]})
            if request.completed_at < current["started_at"]:
                raise VideoPilotError("pilot_attempt_completion_precedes_start")
            merged_metrics = dict(current["metrics"] or {})
            merged_metrics.update(request.metrics)
            attempt = conn.execute(
                """UPDATE football_brief.video_pilot_attempts SET
                       status=%s,completed_at=%s,wall_clock_ms=%s,gpu_active_ms=%s,
                       peak_vram_mib=%s,peak_system_ram_mib=%s,average_gpu_temperature_c=%s,
                       peak_gpu_temperature_c=%s,average_gpu_power_w=%s,peak_gpu_power_w=%s,
                       output_asset_id=%s,external_cost_usd=%s,failure_code=%s,failure_message=%s,
                       metrics=%s::jsonb WHERE id=%s RETURNING *""",
                (
                    request.status.value,
                    request.completed_at,
                    request.wall_clock_ms,
                    request.gpu_active_ms,
                    request.peak_vram_mib,
                    request.peak_system_ram_mib,
                    request.average_gpu_temperature_c,
                    request.peak_gpu_temperature_c,
                    request.average_gpu_power_w,
                    request.peak_gpu_power_w,
                    request.output_asset_id,
                    request.external_cost_usd,
                    request.failure_code,
                    request.failure_message,
                    _json(merged_metrics),
                    attempt_id,
                ),
            ).fetchone()
            if request.status != PilotAttemptStatus.SUCCEEDED:
                conn.execute(
                    "UPDATE football_brief.video_pilot_cases SET status='ready' WHERE id=%s AND status<>'completed'",
                    (current["pilot_case_id"],),
                )
        return {"ok": True, "kind": "video_pilot_attempt_completed", "attempt": dict(attempt)}

    def review_attempt(self, attempt_id: UUID, request: PilotAttemptReviewRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            attempt = conn.execute(
                """SELECT a.*,c.status AS case_status,c.pilot_item_id,i.status AS item_status
                   FROM football_brief.video_pilot_attempts a
                   JOIN football_brief.video_pilot_cases c ON c.id=a.pilot_case_id
                   JOIN football_brief.video_pilot_items i ON i.id=c.pilot_item_id
                   WHERE a.id=%s FOR UPDATE OF a,c,i""",
                (attempt_id,),
            ).fetchone()
            if not attempt:
                raise VideoPilotError("pilot_attempt_not_found")
            if attempt["status"] != "succeeded":
                raise VideoPilotError("only_succeeded_pilot_attempts_are_reviewable")
            if attempt["case_status"] == "completed" or attempt["item_status"] == "completed":
                raise VideoPilotError("pilot_case_already_has_accepted_output")
            review = conn.execute(
                """INSERT INTO football_brief.video_pilot_attempt_reviews
                   (pilot_attempt_id,decision,motion_quality,reference_consistency,artifact_control,
                    composition_quality,defect_tags,notes,reviewed_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::text[],%s,%s) RETURNING *""",
                (
                    attempt_id,
                    request.decision.value,
                    request.motion_quality,
                    request.reference_consistency,
                    request.artifact_control,
                    request.composition_quality,
                    list(request.defect_tags),
                    request.notes.strip(),
                    actor,
                ),
            ).fetchone()
            case_status = "completed" if request.decision == PilotReviewDecision.ACCEPTED else "ready"
            conn.execute(
                "UPDATE football_brief.video_pilot_cases SET status=%s WHERE id=%s",
                (case_status, attempt["pilot_case_id"]),
            )
            remaining = int(
                conn.execute(
                    """SELECT count(*)::int AS value FROM football_brief.video_pilot_cases
                       WHERE pilot_item_id=%s AND status NOT IN ('completed','cancelled')""",
                    (attempt["pilot_item_id"],),
                ).fetchone()["value"]
            )
            total = int(
                conn.execute(
                    "SELECT count(*)::int AS value FROM football_brief.video_pilot_cases WHERE pilot_item_id=%s",
                    (attempt["pilot_item_id"],),
                ).fetchone()["value"]
            )
            item_status = "completed" if total > 0 and remaining == 0 else "production"
            conn.execute(
                "UPDATE football_brief.video_pilot_items SET status=%s WHERE id=%s",
                (item_status, attempt["pilot_item_id"]),
            )
        return {"ok": True, "kind": "video_pilot_attempt_reviewed", "review": dict(review)}

    def list_runs(self, *, limit: int = 100) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise VideoPilotError("invalid_pilot_run_limit")
        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM football_brief.video_pilot_runs ORDER BY created_at DESC,id DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return {"ok": True, "kind": "video_pilot_runs", "runs": [dict(row) for row in rows]}

    def detail(self, run_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            run = conn.execute("SELECT * FROM football_brief.video_pilot_runs WHERE id=%s", (run_id,)).fetchone()
            if not run:
                raise VideoPilotError("pilot_run_not_found")
            items = conn.execute(
                "SELECT * FROM football_brief.video_pilot_items WHERE pilot_run_id=%s ORDER BY item_key,id",
                (run_id,),
            ).fetchall()
            cases = conn.execute(
                "SELECT * FROM football_brief.video_pilot_cases WHERE pilot_run_id=%s ORDER BY case_key,id",
                (run_id,),
            ).fetchall()
            attempts = conn.execute(
                """SELECT a.* FROM football_brief.video_pilot_attempts a
                   JOIN football_brief.video_pilot_cases c ON c.id=a.pilot_case_id
                   WHERE c.pilot_run_id=%s ORDER BY c.case_key,a.attempt_number""",
                (run_id,),
            ).fetchall()
            reviews = conn.execute(
                """SELECT rv.* FROM football_brief.video_pilot_attempt_reviews rv
                   JOIN football_brief.video_pilot_attempts a ON a.id=rv.pilot_attempt_id
                   JOIN football_brief.video_pilot_cases c ON c.id=a.pilot_case_id
                   WHERE c.pilot_run_id=%s ORDER BY rv.reviewed_at,rv.id""",
                (run_id,),
            ).fetchall()
            reports = conn.execute(
                "SELECT * FROM football_brief.video_pilot_reports WHERE pilot_run_id=%s ORDER BY version DESC",
                (run_id,),
            ).fetchall()
        return {
            "ok": True,
            "kind": "video_pilot_run_detail",
            "run": dict(run),
            "items": [dict(row) for row in items],
            "cases": [dict(row) for row in cases],
            "attempts": [dict(row) for row in attempts],
            "reviews": [dict(row) for row in reviews],
            "reports": [dict(row) for row in reports],
        }

    def report(self, run_id: UUID) -> dict[str, Any]:
        return {"ok": True, "kind": "video_pilot_report_preview", "report": compile_pilot_report(self.detail(run_id))}

    def snapshot_report(self, run_id: UUID, *, actor: str) -> dict[str, Any]:
        report = self.report(run_id)["report"]
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            version = int(
                conn.execute(
                    "SELECT COALESCE(max(version),0)+1 AS value FROM football_brief.video_pilot_reports WHERE pilot_run_id=%s",
                    (run_id,),
                ).fetchone()["value"]
            )
            row = conn.execute(
                """INSERT INTO football_brief.video_pilot_reports
                   (pilot_run_id,version,report_snapshot,generated_by)
                   VALUES (%s,%s,%s::jsonb,%s) RETURNING *""",
                (run_id, version, _json(report), actor),
            ).fetchone()
        return {"ok": True, "kind": "video_pilot_report_snapshotted", "report": dict(row)}

    def close_run(self, run_id: UUID, *, actor: str) -> dict[str, Any]:
        preview = self.report(run_id)["report"]
        if not preview["acceptance_ready"]:
            raise VideoPilotError("pilot_run_acceptance_not_ready", details={"reasons": preview["insufficiency_reasons"]})
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            run = conn.execute(
                "SELECT * FROM football_brief.video_pilot_runs WHERE id=%s FOR UPDATE",
                (run_id,),
            ).fetchone()
            if not run:
                raise VideoPilotError("pilot_run_not_found")
            if run["status"] == "closed":
                return {"ok": True, "kind": "video_pilot_run_closed", "reused": True, "run": dict(run)}
            if run["status"] != "running":
                raise VideoPilotError("pilot_run_not_closable", details={"status": run["status"]})
            updated = conn.execute(
                """UPDATE football_brief.video_pilot_runs
                   SET status='closed',closed_by=%s,closed_at=now() WHERE id=%s RETURNING *""",
                (actor, run_id),
            ).fetchone()
        snapshot = self.snapshot_report(run_id, actor=actor)
        return {"ok": True, "kind": "video_pilot_run_closed", "reused": False, "run": dict(updated), "report": snapshot["report"]}

    def _editable_run(self, conn: Any, run_id: UUID) -> dict[str, Any]:
        run = conn.execute(
            "SELECT id,status FROM football_brief.video_pilot_runs WHERE id=%s FOR SHARE",
            (run_id,),
        ).fetchone()
        if not run:
            raise VideoPilotError("pilot_run_not_found")
        if run["status"] not in {"planned", "running"}:
            raise VideoPilotError("pilot_run_not_editable", details={"status": run["status"]})
        return dict(run)

    def _validate_attempt_bindings(self, conn: Any, request: PilotAttemptCreateRequest) -> None:
        if request.renderer_catalogue_entry_id:
            renderer = conn.execute(
                "SELECT id,provider_key,model_key,status FROM football_brief.renderer_catalogue_entries WHERE id=%s",
                (request.renderer_catalogue_entry_id,),
            ).fetchone()
            if not renderer:
                raise VideoPilotError("renderer_catalogue_entry_not_found")
            if renderer["status"] != "active":
                raise VideoPilotError("renderer_catalogue_entry_not_active")
            if str(renderer["provider_key"]) != request.provider_key or str(renderer["model_key"]) != request.model_key:
                raise VideoPilotError("renderer_model_policy_mismatch")
        if request.generation_job_id and not conn.execute(
            "SELECT id FROM football_brief.generation_jobs WHERE id=%s", (request.generation_job_id,)
        ).fetchone():
            raise VideoPilotError("generation_job_not_found")

    def _active_policy(self, conn: Any, provider_key: str, model_key: str) -> dict[str, Any]:
        row = conn.execute(
            """SELECT * FROM football_brief.video_model_use_policies
               WHERE provider_key=%s AND model_key=%s AND status='active' ORDER BY version DESC LIMIT 1""",
            (provider_key.strip().lower(), model_key.strip()),
        ).fetchone()
        if not row:
            raise VideoPilotError(
                "video_model_use_policy_not_found",
                details={"provider_key": provider_key, "model_key": model_key},
            )
        return dict(row)

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        if not conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone():
            raise VideoPilotError("active_operator_required")

    @staticmethod
    def _validate_snapshots(**snapshots: dict[str, Any]) -> None:
        try:
            for name, value in snapshots.items():
                assert_snapshot_safe(value, path=name)
        except PilotSnapshotValidationError as exc:
            raise VideoPilotError("pilot_snapshot_contains_sensitive_field", details={"path": exc.path}) from exc
