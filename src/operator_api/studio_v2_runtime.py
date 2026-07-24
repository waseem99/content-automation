from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.application.audio.models import AudioInitializeRequest
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.portfolio_service import PortfolioService
from src.application.production_workflow_service import ProductionWorkflowError, ProductionWorkflowService
from src.application.scripts.models import ScriptAdapterMode, ScriptGenerateRequest
from src.application.visuals.models import VisualProjectInitializeRequest
from src.application.visuals.service import VisualProjectError
from src.application.visuals.validated_service import ValidatedVisualProjectService
from src.infrastructure.database.connection import Database
from src.operations.job_logging import ObservedGenerationJobService as GenerationJobService
from src.operations.local_pipeline import _seed
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class StudioCreateContentRequest(BaseModel):
    brand_id: UUID
    title: str = Field(min_length=3, max_length=240)
    topic: str = Field(min_length=3, max_length=3000)
    objective: str = Field(default="", max_length=2000)
    audience: str = Field(default="", max_length=1000)
    platform: str = Field(default="facebook", min_length=2, max_length=80)
    format_name: str = Field(default="vertical_short", min_length=2, max_length=80)
    duration_seconds: int = Field(default=45, ge=10, le=600)
    language: str = Field(default="en-US", min_length=2, max_length=40)
    scheduled_for: date
    notes: str = Field(default="", max_length=5000)
    generate_script: bool = True
    starting_point: Literal["manual_topic", "suggestion", "approved_plan"] = "manual_topic"


class StudioStartProductionRequest(BaseModel):
    include_audio: bool = True
    include_visuals: bool = True


class StudioV2Service:
    """Thin UI orchestration over the existing portfolio, workflow, and queue services."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.portfolio = PortfolioService(database)
        self.workflows = ProductionWorkflowService(database)
        self.jobs = GenerationJobService(database)
        self.audio = AudioProductionService(database)
        self.visuals = ValidatedVisualProjectService(database)
        self.worker_id = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer")
        self.ollama_endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.kokoro_model = os.getenv("KOKORO_MODEL_ID", "hexgrad/Kokoro-82M")
        self.visual_model = os.getenv("LOCAL_VISUAL_MODEL_ID", "sdxl-base-1.0")

    def overview(self, *, brand_ids: set[str] | None) -> dict[str, Any]:
        brands = self.portfolio.list_brands(active_only=True)
        if brand_ids is not None:
            brands = [brand for brand in brands if str(brand["id"]) in brand_ids]
        items = self.portfolio.queue()
        if brand_ids is not None:
            items = [item for item in items if str(item["brand_id"]) in brand_ids]

        states: list[dict[str, Any]] = []
        for item in items[:50]:
            try:
                state = self.content_state(UUID(str(item["id"])))
            except Exception as exc:  # overview must remain available if one legacy record is malformed
                state = {
                    "item": item,
                    "status": "blocked",
                    "status_label": "Needs attention",
                    "next_actions": [],
                    "blockers": [{"code": "state_unavailable", "message": f"{type(exc).__name__}: {exc}"}],
                    "jobs": [],
                }
            states.append(state)

        with self.database.connection() as conn:
            if brand_ids is None:
                job_rows = conn.execute(
                    """SELECT status,count(*)::int AS count FROM football_brief.generation_jobs
                       WHERE status = ANY(%s::text[]) GROUP BY status""",
                    (["queued", "running", "failed", "dead_letter"],),
                ).fetchall()
            elif not brand_ids:
                job_rows = []
            else:
                job_rows = conn.execute(
                    """SELECT gj.status,count(*)::int AS count
                       FROM football_brief.generation_jobs gj
                       JOIN football_brief.portfolio_content pc ON pc.id=gj.portfolio_content_id
                       JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                       WHERE gj.status = ANY(%s::text[]) AND mp.brand_id = ANY(%s::uuid[])
                       GROUP BY gj.status""",
                    (["queued", "running", "failed", "dead_letter"], list(brand_ids)),
                ).fetchall()
        job_counts = {str(row["status"]): int(row["count"]) for row in job_rows}
        return {
            "ok": True,
            "kind": "studio_v2_overview",
            "counts": {
                "brands": len(brands),
                "content": len(items),
                "awaiting_review": sum(1 for state in states if state["status"] == "awaiting_review"),
                "in_production": sum(1 for state in states if state["status"] == "in_production"),
                "failed_jobs": job_counts.get("failed", 0) + job_counts.get("dead_letter", 0),
                "active_jobs": job_counts.get("queued", 0) + job_counts.get("running", 0),
            },
            "brands": brands,
            "attention": [state for state in states if state["status"] in {"blocked", "awaiting_review", "failed"}][:12],
            "recent": states[:12],
            "job_counts": job_counts,
        }

    def create_content(self, request: StudioCreateContentRequest, *, actor: str) -> dict[str, Any]:
        brand = self._brand(request.brand_id)
        month_start = request.scheduled_for.replace(day=1)
        plan = self.portfolio.create_month_plan(
            brand_id=request.brand_id,
            month_start=month_start,
            target_count=int(brand["monthly_target"]),
            strategy={
                "source": "creator_studio_v2",
                "starting_point": request.starting_point,
                "objective": request.objective,
                "audience": request.audience,
                "platform": request.platform,
                "duration_seconds": request.duration_seconds,
                "language": request.language,
            },
            created_by=actor,
        )
        if not plan.get("ok"):
            raise HTTPException(status_code=422, detail=plan.get("error") or "plan_creation_failed")
        created = self.portfolio.add_content(
            plan_id=plan["plan"]["id"],
            brand_slug=str(brand["slug"]),
            scheduled_for=request.scheduled_for,
            title=request.title,
            concept=request.topic,
            format_name=request.format_name,
        )
        if not created.get("ok"):
            if created.get("duplicate"):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "duplicate_content", "match": created.get("match")},
                )
            raise HTTPException(status_code=422, detail=created.get("error") or "content_creation_failed")

        content_id = UUID(str(created["item"]["id"]))
        workflow = self.workflows.initialize(content_id=content_id, actor=actor)
        workflow_id = UUID(str(workflow["workflow_id"]))
        self._accept_manual_brief(
            workflow_id=workflow_id,
            actor=actor,
            brief={
                "objective": request.objective,
                "audience": request.audience,
                "platform": request.platform,
                "duration_seconds": request.duration_seconds,
                "language": request.language,
                "notes": request.notes,
                "starting_point": request.starting_point,
            },
        )
        queued = self.enqueue_script(content_id=content_id, actor=actor) if request.generate_script else None
        return {
            "ok": True,
            "kind": "studio_v2_content_created",
            "content_id": str(content_id),
            "workflow_id": str(workflow_id),
            "script_job": queued,
            "state": self.content_state(content_id),
        }

    def enqueue_script(self, *, content_id: UUID, actor: str) -> dict[str, Any]:
        try:
            workflow = self.workflows.workflow_for_content(content_id=content_id)
        except ProductionWorkflowError as exc:
            if exc.code != "workflow_not_found":
                raise
            created = self.workflows.initialize(content_id=content_id, actor=actor)
            workflow = self.workflows.detail(workflow_id=UUID(str(created["workflow_id"])))
        workflow_id = UUID(str(workflow["workflow"]["id"]))
        if str(workflow["workflow"]["current_stage"]) == "concept_draft":
            item = self.portfolio.detail(content_id)
            self._accept_manual_brief(
                workflow_id=workflow_id,
                actor=actor,
                brief={"starting_point": "existing_content", "topic": item.get("item", {}).get("concept")},
            )

        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id,pc.version,pc.format,pw.id AS workflow_id,
                          pw.current_version_id AS workflow_version_id,
                          b.primary_platform,bp.default_language
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   JOIN football_brief.production_workflow_versions pwv ON pwv.id=pw.current_version_id
                   JOIN football_brief.brand_profiles bp
                     ON bp.id=COALESCE(pc.brand_profile_id,NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid)
                   LEFT JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                   WHERE pc.id=%s AND pw.status='active' AND pw.current_stage='script_draft'
                     AND sd.id IS NULL""",
                (content_id,),
            ).fetchone()
        if row is None:
            state = self.content_state(content_id)
            active = [job for job in state["jobs"] if job["job_type"] == "script" and job["status"] in {"queued", "running", "succeeded"}]
            if active:
                return {"ok": True, "reused": True, "job": active[0]}
            raise HTTPException(
                status_code=422,
                detail={"code": "script_not_queueable", "blockers": state.get("blockers", [])},
            )

        request = ScriptGenerateRequest(
            platform=row["primary_platform"] or "facebook",
            format=row["format"] or "vertical_short",
            language=row["default_language"] or "en-US",
            target_duration_seconds=float(os.getenv("LOCAL_SCRIPT_DURATION_SECONDS", "45")),
            words_per_minute=float(os.getenv("LOCAL_SCRIPT_WORDS_PER_MINUTE", "150")),
            duration_tolerance_percent=10,
            seed=_seed(row["id"], row["version"], self.ollama_model),
            adapter_mode=ScriptAdapterMode.LOCAL_MODEL,
            local_endpoint=self.ollama_endpoint,
            local_model_id=self.ollama_model,
            local_timeout_seconds=int(os.getenv("LOCAL_SCRIPT_TIMEOUT_SECONDS", "120")),
        )
        job_request = GenerationJobEnqueue(
            portfolio_content_id=row["id"],
            content_version=int(row["version"]),
            production_workflow_id=row["workflow_id"],
            production_workflow_version_id=row["workflow_version_id"],
            job_type=GenerationJobType.SCRIPT,
            provider="ollama-local",
            model_id=self.ollama_model,
            preferred_worker_id=self.worker_id,
            priority=50,
            idempotency_key=f"local-script:{row['id']}:v{row['version']}:{self.ollama_model}",
            input_payload={"request": request.model_dump(mode="json")},
            timeout_seconds=max(request.local_timeout_seconds + 30, 60),
            max_attempts=3,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
            legacy_source={"local_pipeline": True, "studio_v2": True, "bounded_batch": True},
        )
        try:
            job = self.jobs.enqueue(job_request, actor=actor)
        except GenerationJobError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "details": exc.details}) from exc
        return {"ok": True, "reused": bool(job.get("reused")), "job": job}

    def start_local_production(
        self,
        *,
        content_id: UUID,
        actor: str,
        include_audio: bool,
        include_visuals: bool,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id,pc.version,sv.id AS script_version_id,
                          ap.id AS audio_id,vp.id AS visual_id,bvp.id AS visual_preset_id
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   LEFT JOIN football_brief.audio_productions ap
                     ON ap.portfolio_content_id=pc.id AND ap.script_version_id=sv.id
                   LEFT JOIN football_brief.visual_projects vp
                     ON vp.portfolio_content_id=pc.id AND vp.script_version_id=sv.id
                   LEFT JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   LEFT JOIN football_brief.production_workflow_versions pwv ON pwv.id=pw.current_version_id
                   LEFT JOIN football_brief.brand_visual_presets bvp
                     ON bvp.brand_profile_id=COALESCE(pc.brand_profile_id,NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid)
                    AND bvp.preset_key='local-default' AND bvp.status='active'
                   WHERE pc.id=%s AND sv.status='approved'""",
                (content_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=422, detail="approved_script_required")

        audio_result: dict[str, Any] | None = None
        visual_result: dict[str, Any] | None = None
        blocked: list[dict[str, Any]] = []
        if include_audio and row["audio_id"] is None:
            try:
                audio_result = self.audio.initialize(
                    content_id=content_id,
                    request=AudioInitializeRequest(
                        model_id=self.kokoro_model,
                        preferred_worker_id=self.worker_id,
                        timeout_seconds=900,
                        max_attempts=3,
                    ),
                    actor=actor,
                )
            except AudioProductionError as exc:
                blocked.append({"stage": "audio", "code": exc.code, "details": exc.details})
        if include_visuals and row["visual_id"] is None:
            if row["visual_preset_id"] is None:
                blocked.append({"stage": "visual", "code": "active_local_visual_preset_required"})
            else:
                try:
                    visual_result = self.visuals.initialize(
                        content_id=content_id,
                        request=VisualProjectInitializeRequest(
                            visual_preset_id=row["visual_preset_id"],
                            provider="comfyui-sdxl-local",
                            model_id=self.visual_model,
                            candidate_count=int(os.getenv("LOCAL_VISUAL_CANDIDATE_COUNT", "3")),
                            width=int(os.getenv("LOCAL_VISUAL_WIDTH", "704")),
                            height=int(os.getenv("LOCAL_VISUAL_HEIGHT", "1280")),
                            base_seed=_seed(content_id, row["version"], self.visual_model),
                            preferred_worker_id=self.worker_id,
                            timeout_seconds=1800,
                            max_attempts=3,
                        ),
                        actor=actor,
                    )
                except VisualProjectError as exc:
                    blocked.append({"stage": "visual", "code": exc.code, "details": exc.details})
        return {
            "ok": not blocked,
            "kind": "studio_v2_local_production_started",
            "audio": audio_result,
            "visuals": visual_result,
            "blocked": blocked,
            "state": self.content_state(content_id),
            "automatic_approval": False,
            "live_publishing": False,
        }

    def content_state(self, content_id: UUID) -> dict[str, Any]:
        detail = self.portfolio.detail(content_id)
        if not detail.get("ok"):
            raise HTTPException(status_code=404, detail="content_not_found")
        try:
            workflow = self.workflows.workflow_for_content(content_id=content_id)
        except ProductionWorkflowError as exc:
            workflow = None if exc.code == "workflow_not_found" else None

        with self.database.connection() as conn:
            script = conn.execute(
                """SELECT sd.*,sv.version AS current_version,sv.status AS current_version_status,
                          sv.created_by AS current_version_created_by,sv.created_at AS current_version_created_at
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   WHERE sd.portfolio_content_id=%s""",
                (content_id,),
            ).fetchone()
            sections: list[dict[str, Any]] = []
            claims: list[dict[str, Any]] = []
            sources: list[dict[str, Any]] = []
            if script is not None:
                sections = [dict(row) for row in conn.execute(
                    "SELECT * FROM football_brief.script_sections WHERE script_version_id=%s ORDER BY sequence,id",
                    (script["current_version_id"],),
                ).fetchall()]
                claims = [dict(row) for row in conn.execute(
                    "SELECT * FROM football_brief.script_claims WHERE script_version_id=%s ORDER BY sequence,id",
                    (script["current_version_id"],),
                ).fetchall()]
                sources = [dict(row) for row in conn.execute(
                    "SELECT * FROM football_brief.script_sources WHERE script_version_id=%s ORDER BY created_at,id",
                    (script["current_version_id"],),
                ).fetchall()]
            audio = conn.execute(
                """SELECT * FROM football_brief.audio_productions
                   WHERE portfolio_content_id=%s ORDER BY created_at DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
            visual = conn.execute(
                """SELECT * FROM football_brief.visual_projects
                   WHERE portfolio_content_id=%s ORDER BY created_at DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
            jobs = [dict(row) for row in conn.execute(
                """SELECT * FROM football_brief.generation_jobs
                   WHERE portfolio_content_id=%s ORDER BY queued_at DESC,id DESC LIMIT 100""",
                (content_id,),
            ).fetchall()]
            visual_preset = conn.execute(
                """SELECT bvp.id
                   FROM football_brief.portfolio_content pc
                   LEFT JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   LEFT JOIN football_brief.production_workflow_versions pwv ON pwv.id=pw.current_version_id
                   LEFT JOIN football_brief.brand_visual_presets bvp
                     ON bvp.brand_profile_id=COALESCE(pc.brand_profile_id,NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid)
                    AND bvp.preset_key='local-default' AND bvp.status='active'
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()

        payload = {
            "ok": True,
            "kind": "studio_v2_content_state",
            "item": detail["item"],
            "artifacts": detail.get("artifacts", []),
            "approvals": detail.get("approvals", []),
            "workflow": workflow,
            "script": dict(script) if script else None,
            "script_sections": sections,
            "script_claims": claims,
            "script_sources": sources,
            "audio": dict(audio) if audio else None,
            "visual": dict(visual) if visual else None,
            "jobs": jobs,
            "capabilities": {"visual_preset_ready": visual_preset is not None},
        }
        status, label, actions, blockers = self._next_actions(payload)
        payload.update({"status": status, "status_label": label, "next_actions": actions, "blockers": blockers})
        return payload

    def team_keys(self) -> dict[str, Any]:
        if os.getenv("OPS_ENVIRONMENT", "development").strip().lower() == "production":
            raise HTTPException(status_code=403, detail="local_key_reveal_disabled_in_production")
        path = Path(os.getenv("STUDIO_OPERATOR_KEYS_FILE", ".runtime/operator-keys.json")).resolve()
        if not path.is_file():
            raise HTTPException(status_code=404, detail="operator_key_file_not_found")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise HTTPException(status_code=500, detail="operator_key_file_invalid") from exc
        if not isinstance(value, dict):
            raise HTTPException(status_code=500, detail="operator_key_file_invalid")
        items = [
            {"operator_id": str(operator_id), "key": str(key)}
            for operator_id, key in value.items()
            if str(operator_id) != "local-admin" and isinstance(key, str) and key
        ]
        return {"ok": True, "kind": "local_role_keys", "items": items, "admin_key_included": False}

    def _accept_manual_brief(self, *, workflow_id: UUID, actor: str, brief: dict[str, Any]) -> None:
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT w.id,w.portfolio_content_id,w.current_stage,w.current_version_id,w.lock_version,
                          v.status AS version_status,v.snapshot
                   FROM football_brief.production_workflows w
                   JOIN football_brief.production_workflow_versions v ON v.id=w.current_version_id
                   WHERE w.id=%s FOR UPDATE OF w,v""",
                (workflow_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="workflow_not_found")
            if str(row["current_stage"]) != "concept_draft":
                return
            snapshot = dict(row["snapshot"] or {})
            snapshot["brief"] = brief
            conn.execute(
                """UPDATE football_brief.production_workflow_versions
                   SET snapshot=%s::jsonb,last_edited_by=%s WHERE id=%s""",
                (json.dumps(snapshot, default=str), actor, row["current_version_id"]),
            )
            updated = conn.execute(
                """UPDATE football_brief.production_workflows
                   SET current_stage='script_draft',lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s RETURNING id""",
                (workflow_id, row["lock_version"]),
            ).fetchone()
            if updated is None:
                raise HTTPException(status_code=409, detail="workflow_conflict")
            conn.execute(
                """UPDATE football_brief.portfolio_content
                   SET stage='script',
                       brand_profile_id=COALESCE(brand_profile_id,NULLIF(%s,'')::uuid),
                       metadata=metadata || %s::jsonb
                   WHERE id=%s""",
                (
                    str(snapshot.get("brand_profile_id") or ""),
                    json.dumps({"studio_v2_brief": brief}, default=str),
                    row["portfolio_content_id"],
                ),
            )
            conn.execute(
                """INSERT INTO football_brief.production_workflow_stage_history
                   (workflow_id,workflow_version_id,from_stage,to_stage,event,actor,rationale,
                    from_lock_version,to_lock_version)
                   VALUES (%s,%s,'concept_draft','script_draft','manual_brief_accepted',%s,%s,%s,%s)""",
                (
                    workflow_id,
                    row["current_version_id"],
                    actor,
                    "User-authored brief accepted as the script starting point",
                    row["lock_version"],
                    int(row["lock_version"]) + 1,
                ),
            )

    def _brand(self, brand_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT * FROM football_brief.brands WHERE id=%s AND active=true",
                (brand_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="brand_not_found")
        return dict(row)

    @staticmethod
    def _next_actions(payload: dict[str, Any]) -> tuple[str, str, list[dict[str, str]], list[dict[str, str]]]:
        workflow = payload.get("workflow") or {}
        workflow_row = workflow.get("workflow") or {}
        stage = str(workflow_row.get("current_stage") or "")
        script = payload.get("script")
        audio = payload.get("audio")
        visual = payload.get("visual")
        jobs = payload.get("jobs") or []
        artifacts = payload.get("artifacts") or []
        active_jobs = [job for job in jobs if str(job.get("status")) in {"queued", "running"}]
        failed_jobs = [job for job in jobs if str(job.get("status")) in {"failed", "dead_letter"}]
        actions: list[dict[str, str]] = []
        blockers: list[dict[str, str]] = []

        if failed_jobs:
            actions.append({"action": "inspect_failed_jobs", "label": "Resolve failed jobs"})
        if not workflow_row:
            actions.append({"action": "initialize_workflow", "label": "Prepare production workflow"})
            return "blocked", "Workflow not prepared", actions, blockers
        if stage in {"concept_draft", "script_draft"} and script is None:
            script_job = next((job for job in active_jobs if str(job.get("job_type")) == "script"), None)
            if script_job:
                return "in_production", "Script is generating", actions, blockers
            actions.append({"action": "generate_script", "label": "Generate script"})
            return "draft", "Brief ready for script", actions, blockers
        if script is not None:
            script_status = str(script.get("current_version_status") or "")
            if script_status == "working":
                actions.append({"action": "submit_script", "label": "Submit script for review"})
                return "draft", "Script draft ready", actions, blockers
            if script_status in {"changes_requested", "rejected"}:
                actions.append({"action": "revise_script", "label": "Create script revision"})
                return "blocked", "Script changes required", actions, blockers
            if script_status == "in_review":
                actions.append({"action": "review_script", "label": "Review script"})
                return "awaiting_review", "Script awaiting review", actions, blockers
            if script_status == "approved":
                if audio is None or visual is None:
                    if visual is None and not payload.get("capabilities", {}).get("visual_preset_ready"):
                        blockers.append({"code": "visual_preset_required", "message": "Activate the brand's local visual preset before generating visuals."})
                    actions.append({"action": "start_local_production", "label": "Start local audio and visuals"})
                    return "draft", "Script approved", actions, blockers
        if audio is not None and str(audio.get("status")) not in {"approved", "completed"}:
            actions.append({"action": "review_audio", "label": "Review narration"})
            return "awaiting_review", "Narration needs review", actions, blockers
        if visual is not None and str(visual.get("status")) not in {"approved", "completed"}:
            actions.append({"action": "review_visuals", "label": "Review visuals"})
            return "awaiting_review", "Visuals need review", actions, blockers
        preview = next((artifact for artifact in artifacts if str(artifact.get("kind")) in {"preview", "final_video"}), None)
        if preview:
            actions.append({"action": "review_preview", "label": "Review MP4 preview"})
            return "awaiting_review", "Preview ready", actions, blockers
        if active_jobs:
            return "in_production", "Production is running", actions, blockers
        return "draft", "Ready for next production step", actions, blockers


def install_studio_v2_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "studio_v2_routes_installed", False):
        return
    app.state.studio_v2_routes_installed = True
    service = StudioV2Service(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> StudioV2Service:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def content_brand_id(content_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    @app.get("/studio-v2/overview")
    def overview(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {"operator": operator.operator_id, **require_service().overview(brand_ids=visible_brand_ids(operator))}

    @app.post("/studio-v2/content")
    def create_content(
        request: StudioCreateContentRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=str(request.brand_id))
        return {"operator": operator.operator_id, **require_service().create_content(request, actor=operator.operator_id)}

    @app.get("/studio-v2/content/{content_id}/state")
    def content_state(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=content_brand_id(content_id))
        return {"operator": operator.operator_id, **require_service().content_state(content_id)}

    @app.post("/studio-v2/content/{content_id}/generate-script")
    def generate_script(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand_id(content_id))
        result = require_service().enqueue_script(content_id=content_id, actor=operator.operator_id)
        return {"operator": operator.operator_id, **result, "state": require_service().content_state(content_id)}

    @app.post("/studio-v2/content/{content_id}/start-local-production")
    def start_local_production(
        content_id: UUID,
        request: StudioStartProductionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand_id(content_id))
        return {
            "operator": operator.operator_id,
            **require_service().start_local_production(
                content_id=content_id,
                actor=operator.operator_id,
                include_audio=request.include_audio,
                include_visuals=request.include_visuals,
            ),
        }

    @app.get("/studio-v2/team-keys")
    def team_keys(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        return {"operator": operator.operator_id, **require_service().team_keys()}


__all__ = [
    "StudioCreateContentRequest",
    "StudioStartProductionRequest",
    "StudioV2Service",
    "install_studio_v2_routes",
]
