from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService, canonical_fingerprint
from src.application.local_video.models import LocalVideoEnqueueRequest
from src.application.video_pilot.models import ModelUsePreflightRequest
from src.application.video_pilot.policy import evaluate_model_policy
from src.infrastructure.database.connection import Database
from src.p114_video_provider import sha256_file


ROOT = Path(__file__).resolve().parents[3]


class LocalVideoError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


class LocalVideoService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.jobs = GenerationJobService(database)

    def profiles(self) -> dict[str, Any]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT p.*,r.status AS renderer_status,r.health_status,
                          mp.status AS model_policy_status,mp.allowed_use_scopes,
                          mp.allowed_territories,mp.prohibited_territories,
                          mp.evidence_digest AS policy_evidence_digest
                   FROM football_brief.local_video_renderer_profiles p
                   JOIN football_brief.renderer_catalogue_entries r ON r.id=p.renderer_catalogue_entry_id
                   JOIN football_brief.video_model_use_policies mp ON mp.id=p.model_policy_id
                   ORDER BY p.provider_key,p.model_key,p.version DESC"""
            ).fetchall()
        return {"ok": True, "kind": "local_video_profiles", "profiles": [dict(row) for row in rows]}

    def preflight(self, request: LocalVideoEnqueueRequest) -> dict[str, Any]:
        with self.database.connection() as conn:
            profile, policy = self._active_profile_and_policy(conn, request.provider_key, request.model_key)
            asset = self._input_asset(conn, request.input_asset_id)
            self._validate_content_and_case(conn, request)
        entitlement = evaluate_model_policy(
            dict(policy),
            ModelUsePreflightRequest(
                provider_key=request.provider_key,
                model_key=request.model_key,
                distribution_scope=request.distribution_scope,
                release_territories=request.release_territories,
            ),
        )
        reasons = list(entitlement["rejection_reasons"])
        reasons.extend(self._runtime_profile_reasons(profile))
        if asset["asset_type"] != "image":
            reasons.append("local_video_input_must_be_image")
        return {
            "ok": True,
            "kind": "local_video_preflight",
            "accepted": not reasons,
            "rejection_reasons": sorted(set(reasons)),
            "profile": self._profile_snapshot(profile),
            "entitlement": entitlement,
            "input_asset": {
                "id": str(asset["id"]),
                "sha256": asset["sha256"],
                "mime_type": asset["mime_type"],
                "lifecycle_status": asset["lifecycle_status"],
            },
            "external_fee_possible": False,
            "automatic_approval": False,
            "automatic_publishing": False,
        }

    def enqueue(self, request: LocalVideoEnqueueRequest, *, actor: str) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_active_operator(conn, actor)
            profile, policy = self._active_profile_and_policy(conn, request.provider_key, request.model_key)
            asset = self._input_asset(conn, request.input_asset_id)
            self._validate_content_and_case(conn, request)
        preflight = self.preflight(request)
        if not preflight["accepted"]:
            raise LocalVideoError(
                "local_video_preflight_rejected",
                details={"rejection_reasons": preflight["rejection_reasons"]},
            )
        workflow_path = self._workflow_path(profile)
        actual_workflow_hash = sha256_file(workflow_path)
        if actual_workflow_hash != profile["workflow_sha256"]:
            raise LocalVideoError(
                "local_video_workflow_hash_mismatch",
                details={"expected": profile["workflow_sha256"], "actual": actual_workflow_hash},
            )

        model_evidence = {
            "model_policy_id": str(policy["id"]),
            "model_policy_version": int(policy["version"]),
            "model_policy_evidence_digest": policy["evidence_digest"],
            "renderer_catalogue_entry_id": str(profile["renderer_catalogue_entry_id"]),
            "renderer_profile_id": str(profile["id"]),
            "renderer_profile_version": int(profile["version"]),
            "workflow_sha256": profile["workflow_sha256"],
            "model_files": list(profile["model_files"] or []),
        }
        payload = {
            "kind": "p114_local_video_clip",
            "renderer_profile": self._profile_snapshot(profile),
            "model_evidence": model_evidence,
            "input_asset": {
                "id": str(asset["id"]),
                "storage_uri": asset["storage_uri"],
                "sha256": asset["sha256"],
                "mime_type": asset["mime_type"],
            },
            "pilot_case_id": str(request.pilot_case_id) if request.pilot_case_id else None,
            "distribution_scope": request.distribution_scope.value,
            "release_territories": list(request.release_territories),
            "entitlement": preflight["entitlement"],
            "prompt": request.prompt.strip(),
            "negative_prompt": request.negative_prompt.strip(),
            "duration_seconds": str(request.duration_seconds),
            "width": request.width,
            "height": request.height,
            "fps": request.fps,
            "frame_count": request.frame_count,
            "seed": request.seed,
            "inference_steps": request.inference_steps,
            "cfg": str(request.cfg),
            "sampler_name": request.sampler_name,
            "scheduler": request.scheduler,
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
            "automatic_publishing": False,
        }
        job = self.jobs.enqueue(
            GenerationJobEnqueue(
                portfolio_content_id=request.portfolio_content_id,
                content_version=request.content_version,
                job_type=GenerationJobType.LOCAL_CLIP,
                provider="local-comfyui",
                model_id=request.model_key,
                preferred_worker_id=os.getenv(
                    "P114_LOCAL_VIDEO_WORKER_OPERATOR_ID", "p114-local-video-worker"
                ),
                priority=request.priority,
                idempotency_key=request.idempotency_key,
                input_payload=payload,
                timeout_seconds=request.timeout_seconds,
                max_attempts=request.max_attempts,
                estimated_cost_usd=Decimal("0"),
                reserved_cost_usd=Decimal("0"),
                dependency_job_ids=(),
                legacy_source={"p114": True},
            ),
            actor=actor,
        )
        with self.database.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM football_brief.local_video_clip_bindings WHERE generation_job_id=%s",
                (job["id"],),
            ).fetchone()
            if existing:
                if (
                    existing["renderer_profile_id"] != profile["id"]
                    or existing["input_asset_id"] != asset["id"]
                    or existing["workflow_sha256"] != profile["workflow_sha256"]
                ):
                    raise LocalVideoError("local_video_idempotency_binding_conflict")
                binding = existing
            else:
                binding = conn.execute(
                    """INSERT INTO football_brief.local_video_clip_bindings
                       (generation_job_id,renderer_profile_id,input_asset_id,pilot_case_id,
                        distribution_scope,release_territories,workflow_sha256,model_evidence,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s::text[],%s,%s::jsonb,%s) RETURNING *""",
                    (
                        job["id"],
                        profile["id"],
                        asset["id"],
                        request.pilot_case_id,
                        request.distribution_scope.value,
                        list(request.release_territories),
                        profile["workflow_sha256"],
                        json.dumps(model_evidence, sort_keys=True, default=str),
                        actor,
                    ),
                ).fetchone()
        return {
            "ok": True,
            "kind": "local_video_enqueued",
            "job": job,
            "binding": dict(binding),
            "preflight": preflight,
            "input_fingerprint": canonical_fingerprint(payload),
        }

    def detail(self, job_id: UUID) -> dict[str, Any]:
        job = self.jobs.detail(job_id=job_id)
        with self.database.connection() as conn:
            binding = conn.execute(
                """SELECT b.*,p.provider_key,p.model_key,p.version AS renderer_profile_version,
                          a.storage_uri AS output_storage_uri,a.mime_type AS output_mime_type
                   FROM football_brief.local_video_clip_bindings b
                   JOIN football_brief.local_video_renderer_profiles p ON p.id=b.renderer_profile_id
                   LEFT JOIN football_brief.assets a ON a.id=b.output_asset_id
                   WHERE b.generation_job_id=%s""",
                (job_id,),
            ).fetchone()
        if not binding:
            raise LocalVideoError("local_video_binding_not_found")
        return {"ok": True, "kind": "local_video_detail", **job, "binding": dict(binding)}

    @staticmethod
    def _require_active_operator(conn, actor: str) -> None:
        if not conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone():
            raise LocalVideoError("active_operator_required")

    @staticmethod
    def _active_profile_and_policy(conn, provider_key: str, model_key: str):
        profile = conn.execute(
            """SELECT * FROM football_brief.local_video_renderer_profiles
               WHERE provider_key=%s AND model_key=%s AND status='active'
               ORDER BY version DESC LIMIT 1""",
            (provider_key, model_key),
        ).fetchone()
        if not profile:
            raise LocalVideoError(
                "local_video_renderer_not_active",
                details={"provider_key": provider_key, "model_key": model_key},
            )
        policy = conn.execute(
            "SELECT * FROM football_brief.video_model_use_policies WHERE id=%s AND status='active'",
            (profile["model_policy_id"],),
        ).fetchone()
        if not policy:
            raise LocalVideoError("local_video_model_policy_not_active")
        renderer = conn.execute(
            "SELECT status FROM football_brief.renderer_catalogue_entries WHERE id=%s",
            (profile["renderer_catalogue_entry_id"],),
        ).fetchone()
        if not renderer or renderer["status"] != "active":
            raise LocalVideoError("local_video_catalogue_entry_not_active")
        return profile, policy

    @staticmethod
    def _input_asset(conn, asset_id: UUID):
        asset = conn.execute("SELECT * FROM football_brief.assets WHERE id=%s", (asset_id,)).fetchone()
        if not asset:
            raise LocalVideoError("local_video_input_asset_not_found")
        if asset["lifecycle_status"] not in {"approved", "internal_only"}:
            raise LocalVideoError(
                "local_video_input_asset_not_eligible",
                details={"lifecycle_status": asset["lifecycle_status"]},
            )
        return asset

    @staticmethod
    def _validate_content_and_case(conn, request: LocalVideoEnqueueRequest) -> None:
        content = conn.execute(
            "SELECT version FROM football_brief.portfolio_content WHERE id=%s",
            (request.portfolio_content_id,),
        ).fetchone()
        if not content:
            raise LocalVideoError("content_not_found")
        if int(content["version"]) != request.content_version:
            raise LocalVideoError(
                "content_version_conflict",
                details={"requested": request.content_version, "current": int(content["version"])},
            )
        if request.pilot_case_id:
            case = conn.execute(
                """SELECT c.id FROM football_brief.video_pilot_cases c
                   JOIN football_brief.video_pilot_items i ON i.id=c.pilot_item_id
                   WHERE c.id=%s AND (i.portfolio_content_id IS NULL OR i.portfolio_content_id=%s)""",
                (request.pilot_case_id, request.portfolio_content_id),
            ).fetchone()
            if not case:
                raise LocalVideoError("local_video_pilot_case_content_mismatch")

    @staticmethod
    def _runtime_profile_reasons(profile) -> list[str]:
        reasons: list[str] = []
        if profile["status"] != "active":
            reasons.append("local_video_renderer_not_active")
        if not profile["workflow_path"] or not profile["workflow_sha256"]:
            reasons.append("local_video_workflow_not_configured")
        if not profile["model_files"]:
            reasons.append("local_video_model_files_not_configured")
        return reasons

    @staticmethod
    def _profile_snapshot(profile) -> dict[str, Any]:
        return {
            "id": str(profile["id"]),
            "provider_key": profile["provider_key"],
            "model_key": profile["model_key"],
            "version": int(profile["version"]),
            "status": profile["status"],
            "renderer_catalogue_entry_id": str(profile["renderer_catalogue_entry_id"]),
            "model_policy_id": str(profile["model_policy_id"]),
            "workflow_path": profile["workflow_path"],
            "workflow_sha256": profile["workflow_sha256"],
            "model_files": list(profile["model_files"] or []),
            "default_settings": dict(profile["default_settings"] or {}),
        }

    @staticmethod
    def _workflow_path(profile) -> Path:
        configured = Path(str(profile["workflow_path"])).resolve()
        if configured != ROOT and ROOT not in configured.parents:
            raise LocalVideoError("local_video_workflow_path_outside_repository")
        if not configured.is_file():
            raise LocalVideoError("local_video_workflow_file_missing")
        return configured
