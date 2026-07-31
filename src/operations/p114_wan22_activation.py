from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.local_video.manifest import (
    canonical_sha256,
    load_manifest,
    resolve_workflow_path,
    select_resolution,
    sha256_file,
    validate_workflow,
    verify_comfyui_commit,
    verify_model_bundle,
)
from src.application.local_video.provider import ComfyUILocalVideoProvider
from src.application.renderers.models import (
    RendererAdapterKind,
    RendererEntryRequest,
    RendererHealth,
    RendererHealthRequest,
    RendererOperation,
)
from src.application.renderers.service import RendererCatalogueService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.local_video_worker import LocalVideoGenerationWorker
from src.operations.p113_model_policy_onboarding import onboard as onboard_model_policies


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "config" / "local-video-workflows" / "wan22-ti2v-5b.manifest.json"
DEFAULT_MODEL_ROOT = Path("D:/ComfyUI/App/models")


def _manifest_path() -> Path:
    value = os.getenv("P114_MANIFEST_PATH", str(DEFAULT_MANIFEST))
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _model_root() -> Path:
    return Path(os.getenv("P114_MODEL_ROOT", str(DEFAULT_MODEL_ROOT))).resolve()


def _comfyui_root() -> Path:
    return Path(os.getenv("P114_COMFYUI_ROOT", str(DEFAULT_MODEL_ROOT.parent))).resolve()


def _load_manifest() -> tuple[Path, dict[str, Any]]:
    path = _manifest_path()
    if not path.is_file():
        raise RuntimeError(f"P114 manifest is unavailable: {path}")
    return path, load_manifest(path)


def _workflow_path(manifest: dict[str, Any]) -> Path:
    return resolve_workflow_path(
        manifest,
        repository_root=ROOT,
        approved_root=ROOT / "config" / "local-video-workflows",
    )


def preflight(*, require_empty_queue: bool = True) -> dict[str, Any]:
    manifest_path, manifest = _load_manifest()
    workflow_path = _workflow_path(manifest)
    workflow_result = validate_workflow(manifest, workflow_path=workflow_path)
    actual_workflow_sha = str(workflow_result["workflow_sha256"])

    comfyui_result = verify_comfyui_commit(
        _comfyui_root(),
        str(manifest.get("tested_comfyui_commit") or ""),
    )

    model_root = _model_root()
    model_result = verify_model_bundle(manifest, model_root=model_root)
    bundle_sha = str(model_result["bundle_sha256"])
    verified_files = list(model_result["files"])

    provider = ComfyUILocalVideoProvider(
        base_url=os.getenv("P114_COMFYUI_BASE_URL", "http://127.0.0.1:8188")
    )
    try:
        health = provider.health()
        nodes = provider.validate_nodes({str(value) for value in manifest.get("required_nodes") or []})
        queue_response = provider.client.get("/queue")
        queue_response.raise_for_status()
        queue = queue_response.json()
        running = len(queue.get("queue_running") or [])
        pending = len(queue.get("queue_pending") or [])
        if require_empty_queue and (running or pending):
            raise RuntimeError("ComfyUI queue must be empty before P114 activation or proof")
    finally:
        provider.client.close()

    return {
        "ok": True,
        "kind": "p114_wan22_preflight",
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "workflow_path": str(workflow_path),
        "workflow_sha256": actual_workflow_sha,
        "model_root": str(model_root),
        "model_bundle_sha256": bundle_sha,
        "model_files": verified_files,
        "required_nodes": nodes["required_nodes"],
        "comfyui_checkout": comfyui_result,
        "comfyui": health,
        "queue": {"running": running, "pending": pending},
        "hunyuan_enabled": False,
        "external_fee_possible": False,
    }


def _ensure_renderer(
    database: Database,
    *,
    manifest: dict[str, Any],
    actor: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    service = RendererCatalogueService(database)
    with database.connection() as conn:
        active = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE provider_key=%s AND model_key=%s AND operation='image_to_video'
                 AND status='active' ORDER BY version DESC LIMIT 1""",
            (manifest["provider_key"], manifest["model_key"]),
        ).fetchone()
        latest = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE provider_key=%s AND model_key=%s AND operation='image_to_video'
               ORDER BY version DESC LIMIT 1""",
            (manifest["provider_key"], manifest["model_key"]),
        ).fetchone()

    expected_capabilities = {
        "local_comfyui": True,
        "zero_fee": True,
        "workflow_sha256": manifest["workflow_sha256"],
        "model_bundle_sha256": manifest["model_bundle_sha256"],
        "model_files": manifest["model_files"],
        "required_nodes": manifest["required_nodes"],
        "tested_comfyui_commit": manifest["tested_comfyui_commit"],
        "manifest_sha256": manifest_sha256,
        "hunyuan_enabled": False,
    }
    if active and dict(active.get("capabilities") or {}) == expected_capabilities:
        return {"entry": dict(active), "reused": True}

    license_document = dict(manifest["license"])
    request = RendererEntryRequest(
        provider_key=str(manifest["provider_key"]),
        provider_display_name=str(manifest["provider_display_name"]),
        model_key=str(manifest["model_key"]),
        model_display_name=str(manifest["model_display_name"]),
        operation=RendererOperation.IMAGE_TO_VIDEO,
        adapter_kind=RendererAdapterKind.HTTP_API,
        supported_formats=tuple(manifest["supported_formats"]),
        min_duration_seconds=Decimal(str(manifest["min_duration_seconds"])),
        max_duration_seconds=Decimal(str(manifest["max_duration_seconds"])),
        supported_resolutions=tuple(manifest["supported_resolutions"]),
        capabilities=expected_capabilities,
        expected_latency_seconds={},
        pricing={"per_clip_usd": Decimal("0")},
        pricing_currency="USD",
        quality_rating=Decimal("0"),
        commercial_use_allowed=True,
        usage_terms_url=str(license_document["terms_url"]),
        usage_evidence_digest=canonical_sha256(license_document),
        usage_evidence_recorded_at=datetime.now(timezone.utc),
        data_handling={
            "input_transport": "loopback_http",
            "output_storage": "local_only",
            "external_upload": False,
        },
        notes="P114 workstation-validated Wan2.2 TI2V-5B zero-fee renderer.",
        parent_entry_id=latest["id"] if latest else None,
    )
    created = service.create_entry(request=request, actor=actor)["entry"]
    service.observe_health(
        entry_id=created["id"],
        request=RendererHealthRequest(
            status=RendererHealth.HEALTHY,
            checked_by=actor,
            details={
                "preflight": "P114 local ComfyUI loopback and required-node validation passed",
                "manifest_sha256": manifest_sha256,
            },
        ),
        actor=actor,
    )
    activated = service.activate(entry_id=created["id"], actor=actor)["entry"]
    return {"entry": activated, "reused": False}


def _ensure_workflow(
    database: Database,
    *,
    manifest: dict[str, Any],
    renderer_entry_id: UUID,
    policy_id: UUID,
    actor: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    capabilities = {
        "manifest_sha256": manifest_sha256,
        "official_ui_template_sha256": manifest["official_ui_template_sha256"],
        "tested_comfyui_commit": manifest["tested_comfyui_commit"],
        "model_files": manifest["model_files"],
        "required_nodes": manifest["required_nodes"],
        "default_frame_count": manifest["default_frame_count"],
        "hunyuan_enabled": False,
        "automatic_approval": False,
        "automatic_publishing": False,
    }
    with database.transaction() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"p114-workflow:{manifest['provider_key']}:{manifest['model_key']}:{manifest['workflow_key']}",),
        )
        active = conn.execute(
            """SELECT * FROM football_brief.local_video_workflows
               WHERE provider_key=%s AND model_key=%s AND workflow_key=%s AND status='active'
               ORDER BY version DESC LIMIT 1 FOR UPDATE""",
            (manifest["provider_key"], manifest["model_key"], manifest["workflow_key"]),
        ).fetchone()
        if active:
            exact = (
                str(active["workflow_sha256"]) == str(manifest["workflow_sha256"])
                and str(active["checkpoint_sha256"]) == str(manifest["model_bundle_sha256"])
                and active["renderer_catalogue_entry_id"] == renderer_entry_id
                and active["model_policy_id"] == policy_id
                and dict(active.get("capabilities") or {}) == capabilities
            )
            if exact:
                return {"workflow": dict(active), "reused": True}

        latest = conn.execute(
            """SELECT * FROM football_brief.local_video_workflows
               WHERE provider_key=%s AND model_key=%s AND workflow_key=%s
               ORDER BY version DESC LIMIT 1 FOR UPDATE""",
            (manifest["provider_key"], manifest["model_key"], manifest["workflow_key"]),
        ).fetchone()
        version = int(latest["version"]) + 1 if latest else 1
        parent_id = latest["id"] if latest else None
        if active:
            conn.execute(
                """UPDATE football_brief.local_video_workflows
                   SET status='retired',retired_by=%s,retired_at=now() WHERE id=%s""",
                (actor, active["id"]),
            )
        inserted = conn.execute(
            """INSERT INTO football_brief.local_video_workflows
               (provider_key,model_key,workflow_key,version,parent_workflow_id,operation,status,
                workflow_path,workflow_sha256,checkpoint_sha256,renderer_catalogue_entry_id,
                model_policy_id,supported_resolutions,min_duration_seconds,max_duration_seconds,
                default_fps,default_steps,capabilities,created_by)
               VALUES (%s,%s,%s,%s,%s,'image_to_video','draft',%s,%s,%s,%s,%s,%s::jsonb,
                       %s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
            (
                manifest["provider_key"],
                manifest["model_key"],
                manifest["workflow_key"],
                version,
                parent_id,
                manifest["workflow_path"],
                manifest["workflow_sha256"],
                manifest["model_bundle_sha256"],
                renderer_entry_id,
                policy_id,
                json.dumps(manifest["supported_resolutions"]),
                manifest["min_duration_seconds"],
                manifest["max_duration_seconds"],
                manifest["default_fps"],
                manifest["default_steps"],
                json.dumps(capabilities, sort_keys=True),
                actor,
            ),
        ).fetchone()
        activated = conn.execute(
            """UPDATE football_brief.local_video_workflows
               SET status='active',activated_by=%s,activated_at=now()
               WHERE id=%s AND status='draft' RETURNING *""",
            (actor, inserted["id"]),
        ).fetchone()
    return {"workflow": dict(activated), "reused": False}


def onboard() -> dict[str, Any]:
    preflight_result = preflight(require_empty_queue=True)
    policy_result = onboard_model_policies()
    manifest_path, manifest = _load_manifest()
    manifest_sha = sha256_file(manifest_path)
    actor = os.getenv("LOCAL_SUPER_ADMIN_OPERATOR_ID", "local-super-admin")
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            policy = conn.execute(
                """SELECT * FROM football_brief.video_model_use_policies
                   WHERE provider_key=%s AND model_key=%s AND status='active'
                   ORDER BY version DESC LIMIT 1""",
                (manifest["provider_key"], manifest["model_key"]),
            ).fetchone()
        if not policy:
            raise RuntimeError("active P113 Wan2.2 policy was not created")
        renderer = _ensure_renderer(
            database,
            manifest=manifest,
            actor=actor,
            manifest_sha256=manifest_sha,
        )
        workflow = _ensure_workflow(
            database,
            manifest=manifest,
            renderer_entry_id=renderer["entry"]["id"],
            policy_id=policy["id"],
            actor=actor,
            manifest_sha256=manifest_sha,
        )
    finally:
        database.close()
    return {
        "ok": True,
        "kind": "p114_wan22_onboarding",
        "preflight": preflight_result,
        "policy_onboarding": policy_result,
        "renderer": {"id": str(renderer["entry"]["id"]), "reused": renderer["reused"]},
        "workflow": {"id": str(workflow["workflow"]["id"]), "reused": workflow["reused"]},
        "hunyuan_enabled": False,
        "worker_enabled_by_this_command": False,
        "generation_submitted": False,
    }


def _resolution_for(width: int, height: int, manifest: dict[str, Any]) -> tuple[int, int]:
    return select_resolution(width, height, manifest["supported_resolutions"])


def enqueue_latest(*, limit: int = 1) -> dict[str, Any]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    _, manifest = _load_manifest()
    actor = os.getenv("P114_ENQUEUE_OPERATOR_ID", os.getenv("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer"))
    worker_id = os.getenv("LOCAL_VIDEO_WORKER_OPERATOR_ID", "local-video-worker")
    motion_suffix = os.getenv(
        "P114_MOTION_PROMPT_SUFFIX",
        "Preserve the approved subject and composition. Add subtle natural motion and a slow controlled camera move. No cuts.",
    ).strip()
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        jobs = GenerationJobService(database)
        with database.connection() as conn:
            workflow = conn.execute(
                """SELECT * FROM football_brief.local_video_workflows
                   WHERE provider_key=%s AND model_key=%s AND workflow_key=%s AND status='active'
                   ORDER BY version DESC LIMIT 1""",
                (manifest["provider_key"], manifest["model_key"], manifest["workflow_key"]),
            ).fetchone()
            if not workflow:
                raise RuntimeError("P114 Wan2.2 workflow is not active; run onboard first")
            rows = conn.execute(
                """SELECT pc.id AS portfolio_content_id,pc.version AS content_version,
                          pw.id AS production_workflow_id,pw.current_version_id AS production_workflow_version_id,
                          vp.id AS visual_project_id,vs.id AS visual_shot_id,vs.sequence,
                          vc.id AS visual_candidate_id,vc.asset_id,vc.generation_job_id AS keyframe_job_id,
                          vc.seed,vc.width,vc.height,vc.prompt_snapshot,vc.negative_prompt_snapshot,
                          spe.target_duration_seconds
                   FROM football_brief.visual_shots vs
                   JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
                   JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
                   LEFT JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id AND pw.status='active'
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
                     )
                   ORDER BY vs.updated_at DESC,vs.id
                   LIMIT %s""",
                (str(workflow["id"]), limit),
            ).fetchall()

        enqueued: list[dict[str, Any]] = []
        for row in rows:
            width, height = _resolution_for(int(row["width"]), int(row["height"]), manifest)
            prompt = f"{str(row['prompt_snapshot']).strip()} {motion_suffix}".strip()
            payload = {
                "local_video_workflow_id": str(workflow["id"]),
                "input_keyframe_asset_id": str(row["asset_id"]),
                "visual_project_id": str(row["visual_project_id"]),
                "visual_shot_id": str(row["visual_shot_id"]),
                "visual_candidate_id": str(row["visual_candidate_id"]),
                "prompt": prompt,
                "negative_prompt": str(row["negative_prompt_snapshot"] or ""),
                "seed": int(row["seed"]),
                "width": width,
                "height": height,
                "fps": int(manifest["default_fps"]),
                "frame_count": int(manifest["default_frame_count"]),
                "inference_steps": int(manifest["default_steps"]),
                "distribution_scope": "internal",
                "release_territories": [],
                "target_scene_duration_seconds": float(row["target_duration_seconds"]),
                "automatic_approval": False,
                "automatic_publishing": False,
            }
            idempotency = (
                f"p114-wan22:{row['asset_id']}:{workflow['workflow_sha256']}:"
                f"{width}x{height}:{payload['frame_count']}:{payload['inference_steps']}"
            )
            request = GenerationJobEnqueue(
                portfolio_content_id=row["portfolio_content_id"],
                content_version=int(row["content_version"]),
                production_workflow_id=row["production_workflow_id"],
                production_workflow_version_id=row["production_workflow_version_id"],
                job_type=GenerationJobType.LOCAL_CLIP,
                provider="local-comfyui-video",
                model_id=str(manifest["model_key"]),
                preferred_worker_id=worker_id,
                priority=30,
                idempotency_key=idempotency,
                input_payload=payload,
                timeout_seconds=int(os.getenv("P114_JOB_TIMEOUT_SECONDS", "14400")),
                max_attempts=int(os.getenv("P114_MAX_ATTEMPTS", "2")),
                estimated_cost_usd=Decimal("0"),
                reserved_cost_usd=Decimal("0"),
                dependency_job_ids=(row["keyframe_job_id"],) if row["keyframe_job_id"] else (),
                legacy_source={"p114": True, "auto_selected_approved_keyframe": True},
            )
            job = jobs.enqueue(request, actor=actor)
            enqueued.append(
                {
                    "job_id": str(job["id"]),
                    "content_id": str(row["portfolio_content_id"]),
                    "visual_shot_id": str(row["visual_shot_id"]),
                    "input_keyframe_asset_id": str(row["asset_id"]),
                    "reused": bool(job.get("reused")),
                }
            )
    finally:
        database.close()
    return {
        "ok": True,
        "kind": "p114_enqueue_latest",
        "eligible_count": len(rows),
        "enqueued": enqueued,
        "manual_keyframe_required": False,
        "external_fee_possible": False,
    }


def status() -> dict[str, Any]:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            workflow = conn.execute(
                """SELECT id,provider_key,model_key,workflow_key,version,status,workflow_sha256,
                          checkpoint_sha256,activated_at
                   FROM football_brief.local_video_workflows
                   WHERE provider_key='wan-ai' AND model_key='Wan2.2-TI2V-5B'
                   ORDER BY version DESC LIMIT 1"""
            ).fetchone()
            jobs = conn.execute(
                """SELECT id,status,portfolio_content_id,attempt_count,output_payload,error_code,error_message,
                          queued_at,started_at,completed_at
                   FROM football_brief.generation_jobs WHERE job_type='local_clip'
                   ORDER BY queued_at DESC LIMIT 20"""
            ).fetchall()
            executions = conn.execute(
                """SELECT id,generation_job_id,generation_attempt_id,status,provider_request_id,
                          output_asset_id,wall_clock_ms,gpu_active_ms,external_cost_usd,
                          submitted_at,completed_at
                   FROM football_brief.local_video_executions
                   ORDER BY submitted_at DESC LIMIT 20"""
            ).fetchall()
    finally:
        database.close()
    return {
        "ok": True,
        "kind": "p114_status",
        "worker_enabled": os.getenv("P114_LOCAL_VIDEO_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        "workflow": dict(workflow) if workflow else None,
        "jobs": [dict(row) for row in jobs],
        "executions": [dict(row) for row in executions],
    }


def proof() -> dict[str, Any]:
    onboarding = onboard()
    queued = enqueue_latest(limit=1)
    if not queued["enqueued"]:
        return {
            "ok": True,
            "kind": "p114_supervised_proof",
            "onboarding": onboarding,
            "enqueue": queued,
            "render": None,
            "reason": "no approved selected keyframe is currently eligible",
        }
    os.environ["P114_LOCAL_VIDEO_ENABLED"] = "true"
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = LocalVideoGenerationWorker(database)
    try:
        render = worker.run_once()
    finally:
        worker.provider.client.close()
        database.close()
    return {
        "ok": bool(render.get("ok")),
        "kind": "p114_supervised_proof",
        "onboarding": onboarding,
        "enqueue": queued,
        "render": render,
        "automatic_approval": False,
        "automatic_publishing": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activate and operate the validated P114 Wan2.2 local renderer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    subparsers.add_parser("onboard")
    enqueue_parser = subparsers.add_parser("enqueue-latest")
    enqueue_parser.add_argument("--limit", type=int, default=1)
    subparsers.add_parser("status")
    subparsers.add_parser("proof")
    args = parser.parse_args(argv)

    if args.command == "preflight":
        result = preflight()
    elif args.command == "onboard":
        result = onboard()
    elif args.command == "enqueue-latest":
        result = enqueue_latest(limit=args.limit)
    elif args.command == "status":
        result = status()
    else:
        result = proof()
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
