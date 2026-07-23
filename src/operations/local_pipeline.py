from __future__ import annotations

import hashlib
import json
import os

import httpx
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

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
                    LEFT JOIN football_brief.brand_visual_presets bvp
                      ON bvp.brand_profile_id=pc.brand_profile_id
                     AND bvp.preset_key='local-default' AND bvp.status='active'
                    WHERE sv.status='approved' {brand_sql}""",
                tuple(brand_values),
            ).fetchone()
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
            },
            "capabilities": {
                "ollama_model": self.ollama_model,
                "kokoro_model": self.kokoro_model,
                "visual_model": self.visual_model,
                "comfyui_configured": self._comfyui_configured(),
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
    ) -> dict[str, Any]:
        limit = self._bounded_limit(limit)
        if not include_audio and not include_visuals:
            return self._empty_continuation()
        scoped = self._normalize_brands(brand_ids)
        brand_sql, brand_values = self._brand_filter(scoped, column="mp.brand_id")
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
        audio: list[dict[str, Any]] = []
        visuals: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
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
        return {
            "ok": True,
            "kind": "local_approved_continuation",
            "processed": len(rows),
            "audio_initialized": audio,
            "visuals_initialized": visuals,
            "blocked": blocked,
            "automatic_approval": False,
            "live_publishing": False,
        }

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
    def _empty_continuation() -> dict[str, Any]:
        return {
            "ok": True,
            "kind": "local_approved_continuation",
            "processed": 0,
            "audio_initialized": [],
            "visuals_initialized": [],
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
