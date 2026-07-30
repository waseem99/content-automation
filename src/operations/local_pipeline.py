from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

import httpx

from src.application.audio.models import AudioInitializeRequest
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError, GenerationJobService
from src.application.scripts.models import ScriptAdapterMode, ScriptGenerateRequest
from src.application.visuals.models import VisualProjectInitializeRequest
from src.application.visuals.service import VisualProjectError
from src.application.visuals.validated_service import ValidatedVisualProjectService
from src.infrastructure.database.connection import Database


class LocalPipelineError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _seed(*parts: object) -> int:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


class LocalPipelineService:
    """Bounded local queue controls. This service never approves or publishes content."""

    MAX_BATCH = 20

    def __init__(self, database: Database) -> None:
        self.database = database
        self.jobs = GenerationJobService(database)
        self.audio = AudioProductionService(database)
        self.visuals = ValidatedVisualProjectService(database)
        self.worker_id = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer")
        self.ollama_endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.kokoro_model = os.getenv("KOKORO_MODEL_ID", "hexgrad/Kokoro-82M")
        self.visual_model = os.getenv("LOCAL_VISUAL_MODEL_ID", "sdxl-base-1.0")
        self.preview_model = os.getenv("LOCAL_PREVIEW_MODEL_ID", "ffmpeg-slideshow-v1")
        self.local_video_model = os.getenv("P113_WAN_MODEL_KEY", "Wan2.2-TI2V-5B")

    def status(self, *, brand_ids: Iterable[UUID] | None = None) -> dict[str, Any]:
        scoped = self._normalize_brands(brand_ids)
        brand_sql, brand_values = self._brand_filter(scoped, column="mp.brand_id")
        preview_render_mode = "animated_local_clips" if self._p114_enabled() else "static_keyframes"
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
                    LEFT JOIN football_brief.brand_visual_presets bvp
                      ON bvp.brand_profile_id=pc.brand_profile_id
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
                          AND COALESCE(gj.input_payload->>'render_mode','static_keyframes')=%s
                          AND gj.status IN ('queued','running','succeeded','failed')
                    ) {brand_sql}""",
                (preview_render_mode, *brand_values),
            ).fetchone()["count"]
            jobs = conn.execute(
                f"""SELECT job_type,status,count(*) AS count
                    FROM football_brief.generation_jobs gj
                    JOIN football_brief.portfolio_content pc ON pc.id=gj.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    WHERE gj.job_type = ANY(%s::text[])
                      AND gj.status = ANY(%s::text[]) {brand_sql}
                    GROUP BY job_type,status ORDER BY job_type,status""",
                (
                    [
                        GenerationJobType.SCRIPT.value,
                        GenerationJobType.NARRATION.value,
                        GenerationJobType.KEYFRAME.value,
                        GenerationJobType.LOCAL_CLIP.value,
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
                    JOIN football_brief.brand_profiles bp ON bp.id=pc.brand_profile_id
                    JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
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

    def continue_approved(
        self,
        *,
        limit: int,
        actor: str,
        brand_ids: Iterable[UUID] | None = None,
        include_audio: bool = True,
        include_visuals: bool = True,
        include_local_clips: bool = True,
        include_previews: bool = True,
    ) -> dict[str, Any]:
        limit = self._bounded_limit(limit)
        if not include_audio and not include_visuals and not include_local_clips and not include_previews:
            return self._empty_continuation()
        scoped = self._normalize_brands(brand_ids)
        brand_sql, brand_values = self._brand_filter(scoped, column="mp.brand_id")
        audio: list[dict[str, Any]] = []
        visuals: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []

        if include_audio or include_visuals:
            missing_conditions: list[str] = []
            if include_audio:
                missing_conditions.append("ap.id IS NULL")
            if include_visuals:
                missing_conditions.append("vp.id IS NULL")
            missing_sql = " OR ".join(missing_conditions)
            with self.database.connection() as conn:
                rows = conn.execute(
                    f"""SELECT pc.id,pc.version,sv.id AS script_version_id,
                               ap.id AS audio_id,vp.id AS visual_id,bvp.id AS visual_preset_id
                        FROM football_brief.script_documents sd
                        JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                        JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                        JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                        LEFT JOIN football_brief.audio_productions ap
                          ON ap.portfolio_content_id=pc.id AND ap.script_version_id=sv.id
                        LEFT JOIN football_brief.visual_projects vp
                          ON vp.portfolio_content_id=pc.id AND vp.script_version_id=sv.id
                        LEFT JOIN football_brief.brand_visual_presets bvp
                          ON bvp.brand_profile_id=pc.brand_profile_id
                         AND bvp.preset_key='local-default' AND bvp.status='active'
                        WHERE sv.status='approved' AND ({missing_sql}) {brand_sql}
                        ORDER BY pc.scheduled_for NULLS LAST,pc.created_at,pc.id
                        LIMIT %s""",
                    (*brand_values, limit),
                ).fetchall()
            comfy_ready = self._comfyui_configured()
            for row in rows:
                content_id = row["id"]
                if include_audio and row["audio_id"] is None:
                    try:
                        result = self.audio.initialize(
                            content_id=content_id,
                            request=AudioInitializeRequest(
                                model_id=self.kokoro_model,
                                preferred_worker_id=self.worker_id,
                                timeout_seconds=900,
                                max_attempts=3,
                            ),
                            actor=actor,
                        )
                        audio.append(
                            {
                                "content_id": str(content_id),
                                "production_id": str(result["production"]["id"]),
                            }
                        )
                    except AudioProductionError as exc:
                        blocked.append(
                            {
                                "content_id": str(content_id),
                                "stage": "audio",
                                "code": exc.code,
                                "details": exc.details,
                            }
                        )
                if not include_visuals or row["visual_id"] is not None:
                    continue
                if row["visual_preset_id"] is None:
                    blocked.append(
                        {
                            "content_id": str(content_id),
                            "stage": "visual",
                            "code": "active_local_visual_preset_required",
                        }
                    )
                    continue
                if not comfy_ready:
                    blocked.append(
                        {
                            "content_id": str(content_id),
                            "stage": "visual",
                            "code": "comfyui_not_configured",
                        }
                    )
                    continue
                try:
                    result = self.visuals.initialize(
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
                    visuals.append(
                        {
                            "content_id": str(content_id),
                            "project_id": str(result["project"]["id"]),
                        }
                    )
                except VisualProjectError as exc:
                    blocked.append(
                        {
                            "content_id": str(content_id),
                            "stage": "visual",
                            "code": exc.code,
                            "details": exc.details,
                        }
                    )

        local_clips: list[dict[str, Any]] = []
        if include_local_clips and self._p114_enabled():
            clip_result = self._enqueue_local_clips(limit=limit, actor=actor, brand_ids=scoped)
            local_clips.extend(clip_result["enqueued"])
            blocked.extend(clip_result["blocked"])

        previews: list[dict[str, Any]] = []
        if include_previews:
            preview_result = self._enqueue_previews(limit=limit, actor=actor, brand_ids=scoped)
            previews.extend(preview_result["enqueued"])
            blocked.extend(preview_result["blocked"])

        return {
            "ok": True,
            "kind": "local_approved_continuation",
            "audio_initialized": audio,
            "visuals_initialized": visuals,
            "local_clips_enqueued": local_clips,
            "previews_enqueued": previews,
            "blocked": blocked,
            "automatic_approval": False,
            "live_publishing": False,
        }

    def _enqueue_local_clips(
        self,
        *,
        limit: int,
        actor: str,
        brand_ids: list[UUID] | None,
    ) -> dict[str, Any]:
        brand_sql, brand_values = self._brand_filter(brand_ids, column="mp.brand_id")
        with self.database.connection() as conn:
            workflow = conn.execute(
                """SELECT * FROM football_brief.local_video_workflows
                   WHERE provider_key='wan-ai' AND model_key=%s AND status='active'
                   ORDER BY version DESC LIMIT 1""",
                (self.local_video_model,),
            ).fetchone()
            if not workflow:
                return {
                    "enqueued": [],
                    "blocked": [{"stage": "local_clip", "code": "active_p114_workflow_required"}],
                }
            rows = conn.execute(
                f"""SELECT pc.id AS portfolio_content_id,pc.version AS content_version,
                           pw.id AS production_workflow_id,pw.current_version_id AS production_workflow_version_id,
                           vp.id AS visual_project_id,vs.id AS visual_shot_id,vs.sequence,
                           vc.id AS visual_candidate_id,vc.asset_id,vc.generation_job_id AS keyframe_job_id,
                           vc.seed,vc.width,vc.height,vc.prompt_snapshot,vc.negative_prompt_snapshot,
                           spe.target_duration_seconds
                    FROM football_brief.visual_shots vs
                    JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
                    JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    LEFT JOIN football_brief.production_workflows pw
                      ON pw.portfolio_content_id=pc.id AND pw.status='active'
                    JOIN football_brief.visual_candidates vc ON vc.id=vs.selected_candidate_id
                    JOIN football_brief.assets a ON a.id=vc.asset_id
                    JOIN football_brief.script_scene_plan_entries spe ON spe.id=vs.scene_plan_entry_id
                    WHERE vs.status='approved' AND vc.status='selected'
                      AND a.asset_type='image' AND a.lifecycle_status='approved'
                      AND NOT EXISTS (
                          SELECT 1 FROM football_brief.generation_jobs gj
                          WHERE gj.job_type='local_clip'
                            AND gj.input_payload->>'input_keyframe_asset_id'=vc.asset_id::text
                            AND gj.input_payload->>'local_video_workflow_id'=%s
                            AND gj.status IN ('queued','running','succeeded','failed','dead_letter')
                      ) {brand_sql}
                    ORDER BY vs.updated_at,vs.id LIMIT %s""",
                (str(workflow["id"]), *brand_values, limit),
            ).fetchall()

        supported = list(workflow.get("supported_resolutions") or ())
        fps = int(workflow["default_fps"])
        frame_count = int(dict(workflow.get("capabilities") or {}).get("default_frame_count") or 49)
        steps = int(workflow["default_steps"])
        motion_suffix = os.getenv(
            "P114_MOTION_PROMPT_SUFFIX",
            "Preserve the approved subject and composition. Add subtle natural motion and a slow controlled camera move. No cuts.",
        ).strip()
        worker_id = os.getenv("LOCAL_VIDEO_WORKER_OPERATOR_ID", "local-video-worker")
        enqueued: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in rows:
            portrait = int(row["height"]) >= int(row["width"])
            choices = [
                (int(item["width"]), int(item["height"]))
                for item in supported
                if isinstance(item, dict) and "width" in item and "height" in item
            ]
            matching = [item for item in choices if (item[1] >= item[0]) == portrait]
            if not (matching or choices):
                blocked.append(
                    {
                        "content_id": str(row["portfolio_content_id"]),
                        "stage": "local_clip",
                        "code": "active_p114_resolution_required",
                    }
                )
                continue
            width, height = (matching or choices)[0]
            payload = {
                "local_video_workflow_id": str(workflow["id"]),
                "input_keyframe_asset_id": str(row["asset_id"]),
                "visual_project_id": str(row["visual_project_id"]),
                "visual_shot_id": str(row["visual_shot_id"]),
                "visual_candidate_id": str(row["visual_candidate_id"]),
                "prompt": f"{str(row['prompt_snapshot']).strip()} {motion_suffix}".strip(),
                "negative_prompt": str(row["negative_prompt_snapshot"] or ""),
                "seed": int(row["seed"]),
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "inference_steps": steps,
                "distribution_scope": "internal",
                "release_territories": [],
                "target_scene_duration_seconds": float(row["target_duration_seconds"]),
                "automatic_approval": False,
                "automatic_publishing": False,
            }
            request = GenerationJobEnqueue(
                portfolio_content_id=row["portfolio_content_id"],
                content_version=int(row["content_version"]),
                production_workflow_id=row["production_workflow_id"],
                production_workflow_version_id=row["production_workflow_version_id"],
                job_type=GenerationJobType.LOCAL_CLIP,
                provider="local-comfyui-video",
                model_id=self.local_video_model,
                preferred_worker_id=worker_id,
                priority=30,
                idempotency_key=(
                    f"p114-wan22:{row['asset_id']}:{workflow['workflow_sha256']}:"
                    f"{width}x{height}:{frame_count}:{steps}"
                ),
                input_payload=payload,
                timeout_seconds=int(os.getenv("P114_JOB_TIMEOUT_SECONDS", "14400")),
                max_attempts=int(os.getenv("P114_MAX_ATTEMPTS", "2")),
                estimated_cost_usd=Decimal("0"),
                reserved_cost_usd=Decimal("0"),
                dependency_job_ids=(row["keyframe_job_id"],) if row["keyframe_job_id"] else (),
                legacy_source={"p114": True, "automatic_continuation": True},
            )
            try:
                job = self.jobs.enqueue(request, actor=actor)
                enqueued.append(
                    {
                        "id": str(job["id"]),
                        "content_id": str(row["portfolio_content_id"]),
                        "visual_shot_id": str(row["visual_shot_id"]),
                        "reused": bool(job.get("reused")),
                    }
                )
            except GenerationJobError as exc:
                blocked.append(
                    {
                        "content_id": str(row["portfolio_content_id"]),
                        "stage": "local_clip",
                        "code": exc.code,
                        "details": exc.details,
                    }
                )
        return {"enqueued": enqueued, "blocked": blocked}

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
        render_mode = "animated_local_clips" if self._p114_enabled() else "static_keyframes"
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT pc.id,pc.version,ap.id AS audio_production_id,
                           ap.current_mix_version_id,vp.id AS visual_project_id
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
                          AND COALESCE(gj.input_payload->>'render_mode','static_keyframes')=%s
                          AND gj.status IN ('queued','running','succeeded','failed')
                    ) {brand_sql}
                    ORDER BY pc.scheduled_for NULLS LAST,pc.created_at,pc.id
                    LIMIT %s""",
                (render_mode, *brand_values, limit),
            ).fetchall()
        enqueued: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in rows:
            row_render_mode = render_mode
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
                    """SELECT vc.generation_job_id,vs.sequence,spe.target_duration_seconds,
                              CASE WHEN clip.status='succeeded' THEN clip.id END AS local_clip_job_id,
                              clip.status AS local_clip_status
                       FROM football_brief.visual_shots vs
                       JOIN football_brief.visual_candidates vc ON vc.id=vs.selected_candidate_id
                       JOIN football_brief.generation_jobs gj ON gj.id=vc.generation_job_id
                       JOIN football_brief.script_scene_plan_entries spe ON spe.id=vs.scene_plan_entry_id
                       LEFT JOIN LATERAL (
                           SELECT lc.id,lc.status FROM football_brief.generation_jobs lc
                           WHERE lc.job_type='local_clip'
                             AND lc.provider='local-comfyui-video'
                             AND lc.model_id=%s
                             AND lc.input_payload->>'input_keyframe_asset_id'=vc.asset_id::text
                             AND lc.input_payload->>'local_video_workflow_id'=(
                                 SELECT lvw.id::text FROM football_brief.local_video_workflows lvw
                                 WHERE lvw.provider_key='wan-ai' AND lvw.model_key=%s AND lvw.status='active'
                                 ORDER BY lvw.version DESC LIMIT 1
                             )
                           ORDER BY lc.queued_at DESC,lc.id DESC LIMIT 1
                       ) clip ON true
                       WHERE vs.visual_project_id=%s AND vs.status='approved'
                         AND vc.status='selected' AND gj.status='succeeded'
                       ORDER BY vs.sequence""",
                    (self.local_video_model, self.local_video_model, row["visual_project_id"]),
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
            if self._p114_enabled():
                pending_statuses = {None, "queued", "running"}
                if any(item["local_clip_status"] in pending_statuses for item in scenes):
                    blocked.append(
                        {
                            "content_id": str(row["id"]),
                            "stage": "preview",
                            "code": "local_clips_pending",
                        }
                    )
                    continue
                animated_scene_count = sum(
                    1 for item in scenes if item["local_clip_job_id"] is not None
                )
                if animated_scene_count == len(scenes):
                    row_render_mode = "animated_local_clips"
                elif animated_scene_count > 0:
                    row_render_mode = "hybrid_local_clips"
                else:
                    row_render_mode = "static_keyframes_fallback"
            scene_lineage = [
                {
                    "generation_job_id": str(item["generation_job_id"]),
                    "local_clip_job_id": (
                        str(item["local_clip_job_id"]) if item["local_clip_job_id"] else None
                    ),
                    "local_clip_status": item["local_clip_status"],
                }
                for item in scenes
            ]
            scene_lineage_sha256 = hashlib.sha256(
                json.dumps(scene_lineage, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            request = GenerationJobEnqueue(
                portfolio_content_id=row["id"],
                content_version=int(row["version"]),
                job_type=GenerationJobType.PREVIEW,
                provider="ffmpeg-local",
                model_id=self.preview_model,
                preferred_worker_id=self.worker_id,
                priority=20,
                idempotency_key=(
                    f"local-preview:{row_render_mode}:{row['id']}:v{row['version']}:"
                    f"{row['current_mix_version_id']}:{row['visual_project_id']}:"
                    f"{scene_lineage_sha256}"
                ),
                input_payload={
                    "audio_production_id": str(row["audio_production_id"]),
                    "audio_mix_version_id": str(row["current_mix_version_id"]),
                    "visual_project_id": str(row["visual_project_id"]),
                    "render_mode": row_render_mode,
                    "scene_lineage_sha256": scene_lineage_sha256,
                    "audio_job_ids": [str(item["generation_job_id"]) for item in audio_jobs],
                    "scenes": [
                        {
                            "sequence": int(item["sequence"]),
                            "generation_job_id": str(item["generation_job_id"]),
                            "local_clip_job_id": (
                                str(item["local_clip_job_id"]) if item["local_clip_job_id"] else None
                            ),
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

    def _supervisor_status(self) -> dict[str, Any]:
        runtime_root = Path(os.getenv("LOCAL_RUNTIME_ROOT", ".runtime"))
        heartbeat = runtime_root / "supervisor-heartbeat.json"
        if not heartbeat.exists():
            return {"available": False, "healthy": False, "reason": "heartbeat_missing"}
        try:
            payload = json.loads(heartbeat.read_text(encoding="utf-8-sig"))
            observed = datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
            return {
                "available": True,
                "healthy": age <= 20,
                "age_seconds": round(age, 1),
                "processes": payload.get("processes", {}),
                "ngrok": payload.get("ngrok", {}),
            }
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return {
                "available": True,
                "healthy": False,
                "reason": f"heartbeat_invalid:{type(exc).__name__}",
            }

    def _comfyui_configured(self) -> bool:
        workflow = os.getenv("P68_COMFYUI_WORKFLOW_PATH", "").strip()
        checkpoint = os.getenv("P68_COMFYUI_CHECKPOINT", "").strip()
        if not (workflow and checkpoint and Path(workflow).exists()):
            return False
        base_url = os.getenv("P68_COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
        try:
            with httpx.Client(base_url=base_url, timeout=2.0, trust_env=False) as client:
                response = client.get("/system_stats")
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    @staticmethod
    def _p114_enabled() -> bool:
        return os.getenv("P114_LOCAL_VIDEO_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

    @staticmethod
    def _ffmpeg_configured() -> bool:
        from shutil import which

        configured = os.getenv("LOCAL_FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg"
        return bool(Path(configured).is_file() or which(configured))

    @staticmethod
    def _empty_continuation() -> dict[str, Any]:
        return {
            "ok": True,
            "kind": "local_approved_continuation",
            "audio_initialized": [],
            "visuals_initialized": [],
            "local_clips_enqueued": [],
            "previews_enqueued": [],
            "blocked": [],
            "automatic_approval": False,
            "live_publishing": False,
        }

    @classmethod
    def _bounded_limit(cls, limit: int) -> int:
        if not 1 <= int(limit) <= cls.MAX_BATCH:
            raise LocalPipelineError(
                "local_batch_limit_out_of_range",
                details={"minimum": 1, "maximum": cls.MAX_BATCH},
            )
        return int(limit)

    @staticmethod
    def _normalize_brands(values: Iterable[UUID] | None) -> list[UUID] | None:
        if values is None:
            return None
        return [UUID(str(value)) for value in values]

    @staticmethod
    def _brand_filter(values: list[UUID] | None, *, column: str) -> tuple[str, list[Any]]:
        if values is None:
            return "", []
        if not values:
            return " AND false", []
        return f" AND {column} = ANY(%s::uuid[])", [values]
