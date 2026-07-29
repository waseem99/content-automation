from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobType,
)
from src.application.local_video import (
    ComfyUILocalVideoProvider,
    LocalVideoJobStatus,
    LocalVideoRequest,
)
from src.application.video_pilot.models import DistributionScope, ModelUsePreflightRequest
from src.application.video_pilot.policy import evaluate_model_policy
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.job_logging import ObservedGenerationJobService


SUPPORTED_TYPES = {GenerationJobType.LOCAL_CLIP}
ENABLED_VALUES = {"1", "true", "yes", "on"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _local_video_enabled() -> bool:
    return os.getenv("P114_LOCAL_VIDEO_ENABLED", "false").strip().lower() in ENABLED_VALUES


class LocalVideoGenerationWorker:
    def __init__(self, database: Database) -> None:
        if not _local_video_enabled():
            raise RuntimeError("P114 local video worker is disabled")
        self.database = database
        self.jobs = ObservedGenerationJobService(database)
        self.worker_id = os.getenv("LOCAL_VIDEO_WORKER_OPERATOR_ID", "local-video-worker")
        self.lease_seconds = max(120, int(os.getenv("LOCAL_VIDEO_WORKER_LEASE_SECONDS", "1800")))
        self.poll_seconds = max(1, int(os.getenv("LOCAL_VIDEO_POLL_SECONDS", "3")))
        self.artifact_root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.workflow_root = Path(
            os.getenv("P114_WORKFLOW_ROOT", "config/local-video-workflows")
        ).resolve()
        self.provider = ComfyUILocalVideoProvider(
            base_url=os.getenv("P114_COMFYUI_BASE_URL", "http://127.0.0.1:8188")
        )

    def run_once(self) -> dict[str, Any]:
        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=SUPPORTED_TYPES,
            requested_job_types=SUPPORTED_TYPES,
            providers=("local-comfyui-video",),
            lease_seconds=self.lease_seconds,
        )
        if not claim:
            return {"ok": True, "claimed": False}

        job = claim["job"]
        attempt = claim["attempt"]
        lease_token = claim["lease_token"]
        try:
            output = self._execute(job=job, attempt=attempt, lease_token=lease_token)
            self.jobs.complete(
                GenerationJobCompletion(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    output_payload=output,
                    actual_cost_usd=0,
                    provider_request_id=output["provider_request_id"],
                )
            )
            return {
                "ok": True,
                "claimed": True,
                "job_id": str(job["id"]),
                "attempt_id": str(attempt["id"]),
                "job_type": job["job_type"],
                "output": output,
            }
        except Exception as exc:
            self._mark_execution_failed(attempt_id=attempt["id"], error=exc)
            self.jobs.fail(
                GenerationJobFailure(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    error_code="local_video_execution_failed",
                    error_message=f"{type(exc).__name__}: {exc}"[:5000],
                    retryable=isinstance(exc, (TimeoutError, ConnectionError, OSError)),
                    actual_cost_usd=0,
                    error_details={
                        "job_type": job["job_type"],
                        "provider": "local-comfyui-video",
                        "external_fee_incurred": False,
                    },
                )
            )
            return {
                "ok": False,
                "claimed": True,
                "job_id": str(job["id"]),
                "attempt_id": str(attempt["id"]),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _execute(
        self,
        *,
        job: dict[str, Any],
        attempt: dict[str, Any],
        lease_token: UUID,
    ) -> dict[str, Any]:
        payload = dict(job["input_payload"])
        context = self._load_context(payload)
        request = LocalVideoRequest(
            generation_job_id=job["id"],
            generation_attempt_id=attempt["id"],
            pilot_case_id=UUID(str(payload["pilot_case_id"])) if payload.get("pilot_case_id") else None,
            provider_key=str(context["workflow"]["provider_key"]),
            model_key=str(context["workflow"]["model_key"]),
            workflow_key=str(context["workflow"]["workflow_key"]),
            workflow_path=self._workflow_path(str(context["workflow"]["workflow_path"])),
            workflow_sha256=str(context["workflow"]["workflow_sha256"]),
            checkpoint_sha256=str(context["workflow"]["checkpoint_sha256"]),
            input_image_path=context["input_path"],
            end_image_path=context["end_path"],
            prompt=str(payload["prompt"]),
            negative_prompt=str(payload.get("negative_prompt") or ""),
            seed=int(payload["seed"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            fps=int(payload.get("fps") or context["workflow"]["default_fps"]),
            frame_count=int(payload["frame_count"]),
            inference_steps=int(payload.get("inference_steps") or context["workflow"]["default_steps"]),
            output_prefix=f"p114-video/{job['id']}/{attempt['id']}",
        )
        self.provider.health()
        started = time.monotonic()
        submitted = self.provider.submit(request)
        self._record_execution(
            job=job,
            attempt=attempt,
            request=request,
            context=context,
            provider_request_id=submitted.provider_job_id,
        )

        deadline = time.monotonic() + int(job.get("timeout_seconds") or 3600)
        current = submitted
        next_heartbeat = time.monotonic() + min(60, self.lease_seconds // 3)
        while time.monotonic() < deadline:
            current = self.provider.poll(current)
            if current.status in {
                LocalVideoJobStatus.SUCCEEDED,
                LocalVideoJobStatus.FAILED,
                LocalVideoJobStatus.CANCELLED,
            }:
                break
            if time.monotonic() >= next_heartbeat:
                self.jobs.heartbeat(
                    GenerationJobHeartbeat(
                        job_id=job["id"],
                        attempt_id=attempt["id"],
                        lease_token=lease_token,
                        worker_id=self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )
                )
                self._mark_execution_running(attempt["id"])
                next_heartbeat = time.monotonic() + min(60, self.lease_seconds // 3)
            time.sleep(self.poll_seconds)

        if current.status not in {LocalVideoJobStatus.SUCCEEDED, LocalVideoJobStatus.FAILED, LocalVideoJobStatus.CANCELLED}:
            try:
                self.provider.cancel(current)
            finally:
                raise TimeoutError("local ComfyUI video generation timed out")
        if current.status != LocalVideoJobStatus.SUCCEEDED:
            raise RuntimeError(current.error or f"local video ended as {current.status.value}")

        output_dir = (
            self.artifact_root
            / "jobs"
            / str(job["id"])
            / "attempts"
            / str(attempt["id"])
        )
        output_path = output_dir / "clip.mp4"
        self.provider.download(current, output_path)
        asset_id = self._register_asset(job=job, request=request, output_path=output_path)
        wall_clock_ms = int((time.monotonic() - started) * 1000)
        self._complete_execution(
            attempt_id=attempt["id"],
            output_asset_id=asset_id,
            wall_clock_ms=wall_clock_ms,
        )
        storage_uri = (
            f"local-artifact://jobs/{job['id']}/attempts/"
            f"{attempt['id']}/clip.mp4"
        )
        return {
            "kind": "local_comfyui_video",
            "provider": self.provider.name,
            "provider_request_id": current.provider_job_id,
            "generation_attempt_id": str(attempt["id"]),
            "model_id": request.model_key,
            "workflow_key": request.workflow_key,
            "workflow_sha256": request.workflow_sha256,
            "checkpoint_sha256": request.checkpoint_sha256,
            "storage_path": str(output_path),
            "storage_uri": storage_uri,
            "sha256": _sha256(output_path),
            "mime_type": "video/mp4",
            "size_bytes": output_path.stat().st_size,
            "asset_id": str(asset_id),
            "width": request.width,
            "height": request.height,
            "fps": request.fps,
            "frame_count": request.frame_count,
            "inference_steps": request.inference_steps,
            "external_fee_incurred": False,
            "actual_cost_usd": 0,
            "review_status": "pending",
            "human_review_required": True,
            "automatic_approval": False,
            "automatic_publishing": False,
        }

    def _load_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = UUID(str(payload["local_video_workflow_id"]))
        input_asset_id = UUID(str(payload["input_keyframe_asset_id"]))
        end_asset_id = UUID(str(payload["end_frame_asset_id"])) if payload.get("end_frame_asset_id") else None
        with self.database.connection() as conn:
            workflow = conn.execute(
                """SELECT w.*,p.*,
                          w.id AS workflow_id,w.provider_key AS workflow_provider_key,
                          w.model_key AS workflow_model_key,w.status AS workflow_status,
                          p.id AS policy_id,p.status AS policy_status
                   FROM football_brief.local_video_workflows w
                   JOIN football_brief.video_model_use_policies p ON p.id=w.model_policy_id
                   WHERE w.id=%s""",
                (workflow_id,),
            ).fetchone()
            if not workflow or workflow["workflow_status"] != "active" or workflow["policy_status"] != "active":
                raise RuntimeError("active local video workflow and model policy are required")
            workflow = dict(workflow)
            workflow["id"] = workflow["workflow_id"]
            workflow["provider_key"] = workflow["workflow_provider_key"]
            workflow["model_key"] = workflow["workflow_model_key"]
            input_asset = conn.execute(
                "SELECT * FROM football_brief.assets WHERE id=%s AND lifecycle_status='approved'",
                (input_asset_id,),
            ).fetchone()
            end_asset = (
                conn.execute(
                    "SELECT * FROM football_brief.assets WHERE id=%s AND lifecycle_status='approved'",
                    (end_asset_id,),
                ).fetchone()
                if end_asset_id
                else None
            )
        if not input_asset:
            raise RuntimeError("approved input keyframe asset is required")
        if end_asset_id and not end_asset:
            raise RuntimeError("approved end-frame asset is required")

        scope = DistributionScope(str(payload.get("distribution_scope") or "internal"))
        territories = tuple(str(value) for value in payload.get("release_territories") or ())
        preflight = evaluate_model_policy(
            workflow,
            ModelUsePreflightRequest(
                provider_key=str(workflow["provider_key"]),
                model_key=str(workflow["model_key"]),
                distribution_scope=scope,
                release_territories=territories,
            ),
        )
        if not preflight["accepted"]:
            raise RuntimeError(
                "model-use preflight rejected: " + ",".join(preflight["rejection_reasons"])
            )
        return {
            "workflow": workflow,
            "input_asset": dict(input_asset),
            "end_asset": dict(end_asset) if end_asset else None,
            "input_path": self._asset_path(dict(input_asset)),
            "end_path": self._asset_path(dict(end_asset)) if end_asset else None,
            "preflight": preflight,
        }

    def _asset_path(self, asset: dict[str, Any]) -> Path:
        metadata = dict(asset.get("metadata") or {})
        explicit = metadata.get("storage_path")
        if explicit:
            path = Path(str(explicit)).resolve()
        else:
            uri = str(asset["storage_uri"])
            prefix = "local-artifact://"
            if not uri.startswith(prefix):
                raise RuntimeError("local video input asset must use local-artifact storage")
            path = (self.artifact_root / uri[len(prefix):]).resolve()
        if not path.is_file() or self.artifact_root not in path.parents:
            raise RuntimeError("local video input asset path is unavailable or outside artifact root")
        return path

    def _workflow_path(self, value: str) -> Path:
        path = Path(value).resolve()
        if not path.is_file() or self.workflow_root not in path.parents:
            raise RuntimeError("local video workflow is unavailable or outside the approved workflow root")
        return path

    def _record_execution(
        self,
        *,
        job: dict[str, Any],
        attempt: dict[str, Any],
        request: LocalVideoRequest,
        context: dict[str, Any],
        provider_request_id: str,
    ) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.local_video_executions
                   (generation_job_id,generation_attempt_id,local_video_workflow_id,model_policy_id,
                    pilot_case_id,input_keyframe_asset_id,end_frame_asset_id,prompt_sha256,
                    negative_prompt_sha256,seed,width,height,fps,frame_count,inference_steps,status,
                    provider_request_id,metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'submitted',%s,%s::jsonb,%s)""",
                (
                    job["id"],
                    attempt["id"],
                    context["workflow"]["id"],
                    context["workflow"]["policy_id"],
                    request.pilot_case_id,
                    context["input_asset"]["id"],
                    context["end_asset"]["id"] if context["end_asset"] else None,
                    hashlib.sha256(request.prompt.encode("utf-8")).hexdigest(),
                    hashlib.sha256(request.negative_prompt.encode("utf-8")).hexdigest(),
                    request.seed,
                    request.width,
                    request.height,
                    request.fps,
                    request.frame_count,
                    request.inference_steps,
                    provider_request_id,
                    json.dumps({"model_use_preflight": context["preflight"]}, default=str),
                    self.worker_id,
                ),
            )

    def _mark_execution_running(self, attempt_id: UUID) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.local_video_executions SET status='running' WHERE generation_attempt_id=%s AND status='submitted'",
                (attempt_id,),
            )

    def _complete_execution(self, *, attempt_id: UUID, output_asset_id: UUID, wall_clock_ms: int) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.local_video_executions
                   SET status='succeeded',completed_at=now(),output_asset_id=%s,wall_clock_ms=%s,
                       external_cost_usd=0
                   WHERE generation_attempt_id=%s AND status IN ('submitted','running')""",
                (output_asset_id, wall_clock_ms, attempt_id),
            )

    def _mark_execution_failed(self, *, attempt_id: UUID, error: Exception) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.local_video_executions
                   SET status='failed',completed_at=now(),failure_code=%s,failure_message=%s,
                       external_cost_usd=0
                   WHERE generation_attempt_id=%s AND status IN ('submitted','running')""",
                (type(error).__name__, str(error)[:5000], attempt_id),
            )

    def _register_asset(self, *, job: dict[str, Any], request: LocalVideoRequest, output_path: Path) -> UUID:
        digest = _sha256(output_path)
        storage_uri = (
            f"local-artifact://jobs/{job['id']}/attempts/"
            f"{request.generation_attempt_id}/clip.mp4"
        )
        with self.database.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM football_brief.assets WHERE sha256=%s",
                (digest,),
            ).fetchone()
            if existing:
                return existing["id"]
            row = conn.execute(
                """INSERT INTO football_brief.assets
                   (asset_type,source_type,lifecycle_status,original_filename,storage_uri,sha256,
                    mime_type,size_bytes,metadata,created_by)
                   VALUES ('video','ai_generated','internal_only',%s,%s,%s,'video/mp4',%s,%s::jsonb,%s)
                   RETURNING id""",
                (
                    output_path.name,
                    storage_uri,
                    digest,
                    output_path.stat().st_size,
                    json.dumps(
                        {
                            "generation_job_id": str(job["id"]),
                            "generation_attempt_id": str(request.generation_attempt_id),
                            "provider": self.provider.name,
                            "model_id": request.model_key,
                            "workflow_sha256": request.workflow_sha256,
                            "checkpoint_sha256": request.checkpoint_sha256,
                            "storage_path": str(output_path),
                            "local_only": True,
                            "external_fee_incurred": False,
                            "review_status": "pending",
                            "human_content_review_required": True,
                            "automatic_approval": False,
                        }
                    ),
                    self.worker_id,
                ),
            ).fetchone()
            return row["id"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the dedicated zero-fee local video worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args(argv)

    if not _local_video_enabled():
        print(
            json.dumps(
                {
                    "ok": True,
                    "enabled": False,
                    "claimed": False,
                    "reason": "P114_LOCAL_VIDEO_ENABLED is false",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0

    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = LocalVideoGenerationWorker(database)
    try:
        while True:
            result = worker.run_once()
            print(json.dumps(result, default=str, sort_keys=True), flush=True)
            if args.once:
                break
            time.sleep(max(1, args.poll_seconds))
    finally:
        worker.provider.client.close()
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
