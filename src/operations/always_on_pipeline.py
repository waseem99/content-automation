from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.scripts.models import ScriptAdapterMode, ScriptGenerateRequest
from src.operations.local_pipeline import LocalPipelineService, _seed


class AlwaysOnLocalPipelineService(LocalPipelineService):
    """P104 queue service with pinned workflow/profile and script lineage."""

    def status(self, *, brand_ids: Iterable[UUID] | None = None) -> dict[str, Any]:
        scoped = self._normalize_brands(brand_ids)
        brand_sql, brand_values = self._brand_filter(scoped, column="mp.brand_id")
        with self.database.connection() as conn:
            eligible_scripts = conn.execute(
                f"""SELECT count(*) AS count
                    FROM football_brief.portfolio_content pc
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                    LEFT JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                    WHERE pw.status='active' AND pw.current_stage='script_draft'
                      AND sd.id IS NULL {brand_sql}""",
                tuple(brand_values),
            ).fetchone()["count"]
            approved = conn.execute(
                f"""SELECT
                       count(*) FILTER (WHERE ap.id IS NULL) AS audio_count,
                       count(*) FILTER (WHERE vp.id IS NULL AND bvp.id IS NOT NULL) AS visual_count,
                       count(*) FILTER (WHERE vp.id IS NULL AND bvp.id IS NULL) AS visual_blocked_count
                    FROM football_brief.script_documents sd
                    JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                    JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    LEFT JOIN football_brief.audio_productions ap
                      ON ap.portfolio_content_id=pc.id AND ap.script_version_id=sv.id
                    LEFT JOIN football_brief.visual_projects vp
                      ON vp.portfolio_content_id=pc.id AND vp.script_version_id=sv.id
                    LEFT JOIN football_brief.production_workflows pw
                      ON pw.portfolio_content_id=pc.id
                    LEFT JOIN football_brief.production_workflow_versions pwv
                      ON pwv.id=pw.current_version_id
                    LEFT JOIN football_brief.brand_visual_presets bvp
                      ON bvp.brand_profile_id=COALESCE(
                           pc.brand_profile_id,
                           NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid
                         )
                     AND bvp.preset_key='local-default' AND bvp.status='active'
                    WHERE sv.status='approved' {brand_sql}""",
                tuple(brand_values),
            ).fetchone()
            preview_ready = conn.execute(
                f"""SELECT count(*) AS count
                    FROM football_brief.portfolio_content pc
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    JOIN football_brief.audio_productions ap
                      ON ap.portfolio_content_id=pc.id AND ap.status='approved'
                    JOIN football_brief.audio_mix_versions amv
                      ON amv.id=ap.current_mix_version_id AND amv.status='approved'
                    JOIN football_brief.visual_projects vp
                      ON vp.portfolio_content_id=pc.id AND vp.status='approved'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM football_brief.generation_jobs gj
                        WHERE gj.portfolio_content_id=pc.id
                          AND gj.content_version=pc.version
                          AND gj.job_type='preview'
                          AND gj.status IN ('queued','running','succeeded','failed')
                    ) {brand_sql}""",
                tuple(brand_values),
            ).fetchone()["count"]
            jobs = conn.execute(
                f"""SELECT gj.job_type,gj.status,count(*) AS count
                    FROM football_brief.generation_jobs gj
                    JOIN football_brief.portfolio_content pc ON pc.id=gj.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    WHERE gj.job_type = ANY(%s::text[])
                      AND gj.status = ANY(%s::text[]) {brand_sql}
                    GROUP BY gj.job_type,gj.status ORDER BY gj.job_type,gj.status""",
                (
                    [
                        GenerationJobType.SCRIPT.value,
                        GenerationJobType.NARRATION.value,
                        GenerationJobType.KEYFRAME.value,
                        GenerationJobType.PREVIEW.value,
                    ],
                    ["queued", "running", "failed", "dead_letter"],
                    *brand_values,
                ),
            ).fetchall()
        return {
            "ok": True,
            "kind": "local_pipeline_status",
            "eligible": {
                "scripts": int(eligible_scripts),
                "audio": int(approved["audio_count"] or 0),
                "visuals": int(approved["visual_count"] or 0),
                "visuals_blocked_by_preset": int(approved["visual_blocked_count"] or 0),
                "previews": int(preview_ready or 0),
            },
            "capabilities": {
                "ollama_model": self.ollama_model,
                "kokoro_model": self.kokoro_model,
                "visual_model": self.visual_model,
                "preview_model": self.preview_model,
                "comfyui_configured": self._comfyui_configured(),
                "ffmpeg_configured": self._ffmpeg_configured(),
                "managed_renderer": False,
                "automatic_approval": False,
                "live_publishing": False,
            },
            "supervisor": self._supervisor_status(),
            "jobs": [dict(row) for row in jobs],
        }

    def enqueue_scripts(
        self,
        *,
        limit: int,
        actor: str,
        brand_ids: Iterable[UUID] | None = None,
    ) -> dict[str, Any]:
        limit = self._bounded_limit(limit)
        scoped = self._normalize_brands(brand_ids)
        brand_sql, brand_values = self._brand_filter(scoped, column="mp.brand_id")
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT pc.id,pc.version,pc.format,pw.id AS workflow_id,
                           pw.current_version_id AS workflow_version_id,
                           b.primary_platform,bp.default_language
                    FROM football_brief.portfolio_content pc
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    JOIN football_brief.brands b ON b.id=mp.brand_id
                    JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                    JOIN football_brief.production_workflow_versions pwv
                      ON pwv.id=pw.current_version_id
                    JOIN football_brief.brand_profiles bp
                      ON bp.id=COALESCE(
                           pc.brand_profile_id,
                           NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid
                         )
                    LEFT JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                    WHERE pw.status='active' AND pw.current_stage='script_draft'
                      AND sd.id IS NULL {brand_sql}
                    ORDER BY pc.scheduled_for NULLS LAST,pc.created_at,pc.id
                    LIMIT %s""",
                (*brand_values, limit),
            ).fetchall()
        enqueued: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for row in rows:
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
                legacy_source={"local_pipeline": True, "bounded_batch": True},
            )
            try:
                job = self.jobs.enqueue(job_request, actor=actor)
                enqueued.append(
                    {
                        "id": str(job["id"]),
                        "content_id": str(row["id"]),
                        "reused": bool(job.get("reused")),
                    }
                )
            except GenerationJobError as exc:
                errors.append({"content_id": str(row["id"]), "code": exc.code, "details": exc.details})
        return {
            "ok": not errors,
            "kind": "local_script_batch",
            "requested_limit": limit,
            "eligible_count": len(rows),
            "enqueued": enqueued,
            "errors": errors,
            "automatic_approval": False,
            "live_publishing": False,
        }

    def _enqueue_previews(
        self,
        *,
        limit: int,
        actor: str,
        brand_ids: list[UUID] | None,
    ) -> dict[str, Any]:
        if not self._ffmpeg_configured():
            return {"enqueued": [], "blocked": [{"stage": "preview", "code": "ffmpeg_not_configured"}]}
        brand_sql, brand_values = self._brand_filter(brand_ids, column="mp.brand_id")
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT pc.id,pc.version,ap.id AS audio_production_id,
                           ap.current_mix_version_id,ap.script_version_id,
                           vp.id AS visual_project_id
                    FROM football_brief.portfolio_content pc
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    JOIN football_brief.audio_productions ap
                      ON ap.portfolio_content_id=pc.id AND ap.status='approved'
                    JOIN football_brief.audio_mix_versions amv
                      ON amv.id=ap.current_mix_version_id AND amv.status='approved'
                    JOIN football_brief.visual_projects vp
                      ON vp.portfolio_content_id=pc.id AND vp.status='approved'
                     AND vp.script_version_id=ap.script_version_id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM football_brief.generation_jobs gj
                        WHERE gj.portfolio_content_id=pc.id
                          AND gj.content_version=pc.version
                          AND gj.job_type='preview'
                          AND gj.status IN ('queued','running','succeeded','failed')
                    ) {brand_sql}
                    ORDER BY pc.scheduled_for NULLS LAST,pc.created_at,pc.id
                    LIMIT %s""",
                (*brand_values, limit),
            ).fetchall()
        enqueued: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in rows:
            with self.database.connection() as conn:
                audio_jobs = conn.execute(
                    """SELECT ast.generation_job_id
                       FROM football_brief.audio_segment_takes ast
                       JOIN football_brief.audio_paragraphs apar ON apar.id=ast.paragraph_id
                       JOIN football_brief.generation_jobs gj ON gj.id=ast.generation_job_id
                       WHERE ast.audio_production_id=%s AND ast.status='selected'
                         AND gj.status='succeeded'
                       ORDER BY apar.sequence""",
                    (row["audio_production_id"],),
                ).fetchall()
                scenes = conn.execute(
                    """SELECT vc.generation_job_id,vs.sequence,spe.target_duration_seconds
                       FROM football_brief.visual_shots vs
                       JOIN football_brief.visual_candidates vc ON vc.id=vs.selected_candidate_id
                       JOIN football_brief.generation_jobs gj ON gj.id=vc.generation_job_id
                       JOIN football_brief.script_scene_plan_entries spe ON spe.id=vs.scene_plan_entry_id
                       WHERE vs.visual_project_id=%s AND vs.status='approved'
                         AND vc.status='selected' AND gj.status='succeeded'
                       ORDER BY vs.sequence""",
                    (row["visual_project_id"],),
                ).fetchall()
            if not audio_jobs or not scenes:
                blocked.append(
                    {
                        "content_id": str(row["id"]),
                        "stage": "preview",
                        "code": "approved_audio_and_selected_visuals_required",
                    }
                )
                continue
            request = GenerationJobEnqueue(
                portfolio_content_id=row["id"],
                content_version=int(row["version"]),
                job_type=GenerationJobType.PREVIEW,
                provider="ffmpeg-local",
                model_id=self.preview_model,
                preferred_worker_id=self.worker_id,
                priority=20,
                idempotency_key=(
                    f"local-preview:{row['id']}:v{row['version']}:"
                    f"{row['current_mix_version_id']}:{row['visual_project_id']}"
                ),
                input_payload={
                    "script_version_id": str(row["script_version_id"]),
                    "audio_production_id": str(row["audio_production_id"]),
                    "audio_mix_version_id": str(row["current_mix_version_id"]),
                    "visual_project_id": str(row["visual_project_id"]),
                    "audio_job_ids": [str(item["generation_job_id"]) for item in audio_jobs],
                    "scenes": [
                        {
                            "sequence": int(item["sequence"]),
                            "generation_job_id": str(item["generation_job_id"]),
                            "duration_seconds": float(item["target_duration_seconds"]),
                        }
                        for item in scenes
                    ],
                    "width": int(os.getenv("LOCAL_PREVIEW_WIDTH", "704")),
                    "height": int(os.getenv("LOCAL_PREVIEW_HEIGHT", "1280")),
                    "fps": int(os.getenv("LOCAL_PREVIEW_FPS", "30")),
                },
                timeout_seconds=int(os.getenv("LOCAL_PREVIEW_TIMEOUT_SECONDS", "1800")),
                max_attempts=3,
                estimated_cost_usd=Decimal("0"),
                reserved_cost_usd=Decimal("0"),
                legacy_source={"local_pipeline": True, "deterministic_preview": True},
            )
            try:
                job = self.jobs.enqueue(request, actor=actor)
                enqueued.append(
                    {
                        "id": str(job["id"]),
                        "content_id": str(row["id"]),
                        "reused": bool(job.get("reused")),
                    }
                )
            except GenerationJobError as exc:
                blocked.append(
                    {
                        "content_id": str(row["id"]),
                        "stage": "preview",
                        "code": exc.code,
                        "details": exc.details,
                    }
                )
        return {"enqueued": enqueued, "blocked": blocked}
