from __future__ import annotations

import os
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.production_workflow_service import ProductionWorkflowError
from src.application.scripts.models import ScriptAdapterMode, ScriptGenerateRequest
from src.application.scripts.service import ScriptReviewService
from src.operations.local_pipeline import _seed
from src.operator_api.studio_v2_runtime import StudioV2Service


_ORIGINAL_SCRIPT_CONTEXT = ScriptReviewService._context


def _studio_brief_script_context(
    service: ScriptReviewService,
    content_id: UUID,
) -> dict[str, Any]:
    """Add the user-authored Studio brief to the existing validated script context."""
    context = dict(_ORIGINAL_SCRIPT_CONTEXT(service, content_id))
    with service.database.connection() as conn:
        row = conn.execute(
            "SELECT metadata FROM football_brief.portfolio_content WHERE id=%s",
            (content_id,),
        ).fetchone()
    metadata = dict(row["metadata"] or {}) if row else {}
    brief = metadata.get("studio_v2_brief")
    if not isinstance(brief, dict):
        return context

    concept_parts = [str(context.get("concept") or context.get("title") or "").strip()]
    if str(brief.get("objective") or "").strip():
        concept_parts.append(f"Objective: {str(brief['objective']).strip()}")
    if str(brief.get("audience") or "").strip():
        concept_parts.append(f"Target audience: {str(brief['audience']).strip()}")
    if str(brief.get("notes") or "").strip():
        concept_parts.append(f"Additional producer notes: {str(brief['notes']).strip()}")
    context["concept"] = "\n\n".join(part for part in concept_parts if part)

    existing_audience = context.get("audience")
    audience_context = dict(existing_audience) if isinstance(existing_audience, dict) else {}
    if str(brief.get("audience") or "").strip():
        audience_context["studio_brief"] = str(brief["audience"]).strip()
    context["audience"] = audience_context
    context["studio_brief"] = brief
    return context


def _schema_safe_enqueue_script(
    self: StudioV2Service,
    *,
    content_id: UUID,
    actor: str,
) -> dict[str, Any]:
    """Queue a local script with the exact user-selected Studio configuration."""
    try:
        workflow = self.workflows.workflow_for_content(content_id=content_id)
    except ProductionWorkflowError as exc:
        if exc.code != "workflow_not_found":
            raise
        created = self.workflows.initialize(content_id=content_id, actor=actor)
        workflow = self.workflows.detail(
            workflow_id=UUID(str(created["workflow_id"]))
        )
    workflow_id = UUID(str(workflow["workflow"]["id"]))
    if str(workflow["workflow"]["current_stage"]) == "concept_draft":
        item = self.portfolio.detail(content_id)
        self._accept_manual_brief(
            workflow_id=workflow_id,
            actor=actor,
            brief={
                "starting_point": "existing_content",
                "topic": item.get("item", {}).get("concept"),
            },
        )

    with self.database.connection() as conn:
        row = conn.execute(
            """SELECT pc.id,pc.version,pc.format,pc.metadata,
                      pw.id AS workflow_id,pw.current_version_id AS workflow_version_id,
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
        active = [
            job
            for job in state["jobs"]
            if job["job_type"] == "script"
            and job["status"] in {"queued", "running", "succeeded"}
        ]
        if active:
            return {"ok": True, "reused": True, "job": active[0]}
        raise HTTPException(
            status_code=422,
            detail={
                "code": "script_not_queueable",
                "blockers": state.get("blockers", []),
            },
        )

    metadata = dict(row["metadata"] or {})
    brief = metadata.get("studio_v2_brief")
    if not isinstance(brief, dict):
        brief = {}
    platform = str(brief.get("platform") or row["primary_platform"] or "facebook")
    language = str(brief.get("language") or row["default_language"] or "en-US")
    duration = float(
        brief.get("duration_seconds")
        or os.getenv("LOCAL_SCRIPT_DURATION_SECONDS", "45")
    )
    request = ScriptGenerateRequest(
        platform=platform,
        format=row["format"] or "vertical_short",
        language=language,
        target_duration_seconds=duration,
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
        idempotency_key=(
            f"local-script:{row['id']}:v{row['version']}:{self.ollama_model}"
        ),
        input_payload={"request": request.model_dump(mode="json")},
        timeout_seconds=max(request.local_timeout_seconds + 30, 60),
        max_attempts=3,
        estimated_cost_usd=Decimal("0"),
        reserved_cost_usd=Decimal("0"),
        legacy_source={
            "local_pipeline": True,
            "studio_v2": True,
            "bounded_batch": True,
            "brief_fields_applied": True,
        },
    )
    try:
        job = self.jobs.enqueue(job_request, actor=actor)
    except GenerationJobError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "details": exc.details},
        ) from exc
    return {"ok": True, "reused": bool(job.get("reused")), "job": job}


def _schema_safe_content_state(
    self: StudioV2Service,
    content_id: UUID,
) -> dict[str, Any]:
    """Read one content workspace using only columns guaranteed by P84-P104 migrations."""
    detail = self.portfolio.detail(content_id)
    if not detail.get("ok"):
        raise HTTPException(status_code=404, detail="content_not_found")
    try:
        workflow = self.workflows.workflow_for_content(content_id=content_id)
    except ProductionWorkflowError as exc:
        if exc.code != "workflow_not_found":
            raise
        workflow = None

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
            sections = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_sections
                       WHERE script_version_id=%s ORDER BY sequence,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
            claims = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_claims
                       WHERE script_version_id=%s ORDER BY claim_key,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
            sources = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_sources
                       WHERE script_version_id=%s ORDER BY source_key,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
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
        jobs = [
            dict(row)
            for row in conn.execute(
                """SELECT * FROM football_brief.generation_jobs
                   WHERE portfolio_content_id=%s ORDER BY queued_at DESC,id DESC LIMIT 100""",
                (content_id,),
            ).fetchall()
        ]
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

    payload: dict[str, Any] = {
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
    payload.update(
        {
            "status": status,
            "status_label": label,
            "next_actions": actions,
            "blockers": blockers,
        }
    )
    return payload


def apply_studio_v2_schema_patch() -> None:
    """Install schema-safe readers and Studio brief propagation before route setup."""
    if not getattr(ScriptReviewService, "_studio_v2_context_patch_applied", False):
        ScriptReviewService._context = _studio_brief_script_context  # type: ignore[method-assign]
        ScriptReviewService._studio_v2_context_patch_applied = True  # type: ignore[attr-defined]
    StudioV2Service.enqueue_script = _schema_safe_enqueue_script  # type: ignore[method-assign]
    StudioV2Service.content_state = _schema_safe_content_state  # type: ignore[method-assign]


__all__ = ["apply_studio_v2_schema_patch"]
