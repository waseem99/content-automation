from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobType,
)
from src.application.video_pilot.models import DistributionScope, ModelUsePreflightRequest
from src.application.video_pilot.policy import evaluate_model_policy
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.job_logging import ObservedGenerationJobService
from src.p114_video_provider import (
    ComfyUIVideoProvider,
    LocalVideoGenerationRequest,
    VideoJobStatus,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[2]


class LocalVideoCancelled(RuntimeError):
    pass


@dataclass
class GpuMetrics:
    samples: int = 0
    peak_vram_mib: int | None = None
    temperatures: list[float] = field(default_factory=list)
    powers: list[float] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "peak_vram_mib": self.peak_vram_mib,
            "average_gpu_temperature_c": (
                sum(self.temperatures) / len(self.temperatures) if self.temperatures else None
            ),
            "peak_gpu_temperature_c": max(self.temperatures) if self.temperatures else None,
            "average_gpu_power_w": sum(self.powers) / len(self.powers) if self.powers else None,
            "peak_gpu_power_w": max(self.powers) if self.powers else None,
        }


class GpuSampler:
    def __init__(self, interval_seconds: float = 2.0) -> None:
        self.interval_seconds = interval_seconds
        self.metrics = GpuMetrics()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not shutil.which("nvidia-smi"):
            return
        self._thread = threading.Thread(target=self._run, name="p114-gpu-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return self.metrics.snapshot()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=memory.used,temperature.gpu,power.draw",
                        "--format=csv,noheader,nounits",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    first = result.stdout.strip().splitlines()[0]
                    values = [item.strip() for item in first.split(",")]
                    if len(values) >= 3:
                        self.metrics.samples += 1
                        memory = int(float(values[0]))
                        self.metrics.peak_vram_mib = max(self.metrics.peak_vram_mib or 0, memory)
                        self.metrics.temperatures.append(float(values[1]))
                        self.metrics.powers.append(float(values[2]))
            except Exception:
                pass
            self._stop.wait(self.interval_seconds)


class P114LocalVideoWorker:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.jobs = ObservedGenerationJobService(database)
        self.worker_id = os.getenv("P114_LOCAL_VIDEO_WORKER_OPERATOR_ID", "p114-local-video-worker")
        self.lease_seconds = int(os.getenv("P114_LOCAL_VIDEO_WORKER_LEASE_SECONDS", "1800"))
        self.poll_seconds = max(1.0, float(os.getenv("P114_COMFYUI_POLL_SECONDS", "2")))
        self.artifact_root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).resolve()
        self.comfy_root = Path(os.getenv("P114_COMFYUI_ROOT", "ComfyUI")).resolve()
        self.comfy_url = os.getenv("P114_COMFYUI_BASE_URL", os.getenv("P68_COMFYUI_BASE_URL", "http://127.0.0.1:8188"))
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._hash_cache: dict[tuple[str, int, int], str] = {}

    def run_once(self) -> dict[str, Any]:
        reconciled = self._reconcile_completed_once()
        if reconciled:
            return reconciled
        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=(GenerationJobType.LOCAL_CLIP,),
            requested_job_types=(GenerationJobType.LOCAL_CLIP,),
            providers=("local-comfyui",),
            lease_seconds=self.lease_seconds,
        )
        if not claim:
            return {"ok": True, "claimed": False}
        job = claim["job"]
        attempt = claim["attempt"]
        lease_token = claim["lease_token"]
        stop_heartbeat, heartbeat = self._start_heartbeat(job["id"], attempt["id"], lease_token)
        try:
            output = self._execute(job)
            stop_heartbeat.set()
            heartbeat.join(timeout=5)
            if self._job_status(job["id"]) == "cancelled":
                self._complete_pilot_attempt(job["id"], status="cancelled", output=None, error=None)
                return {"ok": True, "claimed": True, "cancelled": True, "job_id": str(job["id"])}
            self.jobs.complete(
                GenerationJobCompletion(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    output_payload=output,
                    actual_cost_usd=Decimal("0"),
                    provider_request_id=output.get("provider_request_id"),
                )
            )
            try:
                asset_id = self._register_output(job, output)
            except Exception as exc:
                return {
                    "ok": False,
                    "claimed": True,
                    "job_id": str(job["id"]),
                    "registration_pending": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            return {
                "ok": True,
                "claimed": True,
                "job_id": str(job["id"]),
                "asset_id": str(asset_id),
                "output": output,
            }
        except LocalVideoCancelled:
            stop_heartbeat.set()
            heartbeat.join(timeout=5)
            self._complete_pilot_attempt(job["id"], status="cancelled", output=None, error=None)
            return {"ok": True, "claimed": True, "cancelled": True, "job_id": str(job["id"])}
        except Exception as exc:
            stop_heartbeat.set()
            heartbeat.join(timeout=5)
            status = self._job_status(job["id"])
            if status == "running":
                self.jobs.fail(
                    GenerationJobFailure(
                        job_id=job["id"],
                        attempt_id=attempt["id"],
                        lease_token=lease_token,
                        worker_id=self.worker_id,
                        error_code="p114_local_video_execution_failed",
                        error_message=f"{type(exc).__name__}: {exc}"[:5000],
                        retryable=isinstance(exc, (TimeoutError, ConnectionError, OSError, subprocess.SubprocessError)),
                        actual_cost_usd=Decimal("0"),
                        error_details={"external_fee_incurred": False, "job_type": "local_clip"},
                    )
                )
                self._complete_pilot_attempt(
                    job["id"],
                    status="failed",
                    output=None,
                    error=("p114_local_video_execution_failed", f"{type(exc).__name__}: {exc}"[:5000]),
                )
            return {
                "ok": False,
                "claimed": True,
                "job_id": str(job["id"]),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _execute(self, job: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT b.*,p.*,mp.status AS policy_status,mp.provider_key AS policy_provider_key,
                          mp.model_key AS policy_model_key,mp.commercial_use_allowed,
                          mp.allowed_use_scopes,mp.allowed_territories,mp.prohibited_territories,
                          mp.requires_written_clearance,mp.evidence_digest,
                          a.storage_uri AS input_storage_uri,a.sha256 AS input_sha256,
                          a.metadata AS input_metadata
                   FROM football_brief.local_video_clip_bindings b
                   JOIN football_brief.local_video_renderer_profiles p ON p.id=b.renderer_profile_id
                   JOIN football_brief.video_model_use_policies mp ON mp.id=p.model_policy_id
                   JOIN football_brief.assets a ON a.id=b.input_asset_id
                   WHERE b.generation_job_id=%s""",
                (job["id"],),
            ).fetchone()
        if not row:
            raise RuntimeError("local video binding is missing")
        if row["status"] != "active" or row["policy_status"] != "active":
            raise RuntimeError("renderer profile or model policy is not active")
        payload = dict(job["input_payload"] or {})
        if payload.get("kind") != "p114_local_video_clip":
            raise RuntimeError("unexpected local video job payload")
        if str(payload["renderer_profile"]["id"]) != str(row["renderer_profile_id"]):
            raise RuntimeError("renderer profile snapshot mismatch")
        if payload["model_evidence"]["workflow_sha256"] != row["workflow_sha256"]:
            raise RuntimeError("workflow lineage mismatch")
        entitlement = evaluate_model_policy(
            {
                "id": row["model_policy_id"],
                "provider_key": row["policy_provider_key"],
                "model_key": row["policy_model_key"],
                "version": payload["model_evidence"]["model_policy_version"],
                "evidence_digest": row["evidence_digest"],
                "commercial_use_allowed": row["commercial_use_allowed"],
                "allowed_use_scopes": row["allowed_use_scopes"],
                "allowed_territories": row["allowed_territories"],
                "prohibited_territories": row["prohibited_territories"],
                "requires_written_clearance": row["requires_written_clearance"],
            },
            ModelUsePreflightRequest(
                provider_key=row["provider_key"],
                model_key=row["model_key"],
                distribution_scope=DistributionScope(row["distribution_scope"]),
                release_territories=tuple(row["release_territories"] or ()),
            ),
        )
        if not entitlement["accepted"]:
            raise RuntimeError(f"distribution entitlement rejected: {entitlement['rejection_reasons']}")

        workflow = self._repo_file(str(row["workflow_path"]))
        if self._cached_hash(workflow) != row["workflow_sha256"]:
            raise RuntimeError("configured workflow hash no longer matches the active profile")
        verified_models = self._verify_model_files(list(row["model_files"] or []))
        input_path = self._input_path(row)
        if self._cached_hash(input_path) != row["input_sha256"]:
            raise RuntimeError("input asset hash mismatch")

        provider = ComfyUIVideoProvider(
            base_url=self.comfy_url,
            workflow_path=workflow,
            expected_workflow_sha256=row["workflow_sha256"],
        )
        provider.health()
        request = LocalVideoGenerationRequest(
            job_id=str(job["id"]),
            prompt=str(payload["prompt"]),
            negative_prompt=str(payload.get("negative_prompt") or ""),
            seed=int(payload["seed"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            frame_count=int(payload["frame_count"]),
            fps=int(payload["fps"]),
            inference_steps=int(payload["inference_steps"]),
            cfg=float(payload["cfg"]),
            sampler_name=str(payload["sampler_name"]),
            scheduler=str(payload["scheduler"]),
            input_image=input_path,
            output_prefix=f"p114/{job['id']}/clip",
            model_key=str(row["model_key"]),
        )
        sampler = GpuSampler()
        sampler.start()
        current = provider.submit(request)
        try:
            deadline = time.monotonic() + int(job.get("timeout_seconds") or 3600)
            while time.monotonic() < deadline:
                status = self._job_status(job["id"])
                if status == "cancelled":
                    provider.cancel(current)
                    raise LocalVideoCancelled("P87 job was cancelled")
                current = provider.poll(current)
                if current.status in {VideoJobStatus.SUCCEEDED, VideoJobStatus.FAILED}:
                    break
                time.sleep(self.poll_seconds)
            if current.status != VideoJobStatus.SUCCEEDED:
                if current.status == VideoJobStatus.FAILED:
                    raise RuntimeError(current.error or "ComfyUI local video failed")
                provider.cancel(current)
                raise TimeoutError("ComfyUI local video timed out")
            output_dir = self.artifact_root / "p114" / str(job["id"])
            path = provider.download(current, output_dir / "clip.mp4")
        finally:
            gpu = sampler.stop()
        media = self._probe_video(path)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "kind": "local_comfyui_video_clip",
            "storage_path": str(path),
            "storage_uri": f"local-artifact://p114/{job['id']}/{path.name}",
            "local_locator": f"content://p114/{job['id']}/{path.name}",
            "sha256": sha256_file(path),
            "mime_type": "video/mp4" if path.suffix.lower() == ".mp4" else "video/webm",
            "size_bytes": path.stat().st_size,
            "provider": "local-comfyui",
            "model_id": row["model_key"],
            "renderer_profile_id": str(row["renderer_profile_id"]),
            "renderer_profile_version": int(row["version"]),
            "model_policy_id": str(row["model_policy_id"]),
            "workflow_sha256": row["workflow_sha256"],
            "model_files": verified_models,
            "provider_request_id": current.provider_job_id,
            "seed": payload["seed"],
            "width": media["width"],
            "height": media["height"],
            "fps": media["fps"],
            "duration_seconds": media["duration_seconds"],
            "frame_count": payload["frame_count"],
            "inference_steps": payload["inference_steps"],
            "wall_clock_ms": elapsed_ms,
            "gpu_active_ms": elapsed_ms,
            "gpu_metrics": gpu,
            "external_fee_incurred": False,
            "actual_cost_usd": 0,
            "human_review_required": True,
            "automatic_approval": False,
            "automatic_publishing": False,
        }

    def _register_output(self, job: dict[str, Any], output: dict[str, Any]) -> UUID:
        with self.database.transaction() as conn:
            asset = conn.execute("SELECT id FROM football_brief.assets WHERE sha256=%s", (output["sha256"],)).fetchone()
            if not asset:
                asset = conn.execute(
                    """INSERT INTO football_brief.assets
                       (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                        sha256,mime_type,size_bytes,metadata,created_by)
                       VALUES ('video','ai_generated','internal_only',%s,%s,%s,%s,%s,%s::jsonb,%s)
                       RETURNING id""",
                    (
                        Path(output["storage_path"]).name,
                        output["storage_uri"],
                        output["sha256"],
                        output["mime_type"],
                        output["size_bytes"],
                        json.dumps(
                            {
                                "generation_job_id": str(job["id"]),
                                "provider": output["provider"],
                                "model_id": output["model_id"],
                                "renderer_profile_id": output["renderer_profile_id"],
                                "model_policy_id": output["model_policy_id"],
                                "workflow_sha256": output["workflow_sha256"],
                                "model_files": output["model_files"],
                                "gpu_metrics": output["gpu_metrics"],
                                "human_content_review_required": True,
                                "external_fee_incurred": False,
                            },
                            sort_keys=True,
                            default=str,
                        ),
                        self.worker_id,
                    ),
                ).fetchone()
            conn.execute(
                """UPDATE football_brief.local_video_clip_bindings
                   SET output_asset_id=%s,output_sha256=%s,completed_at=now()
                   WHERE generation_job_id=%s AND output_asset_id IS NULL""",
                (asset["id"], output["sha256"], job["id"]),
            )
        self._complete_pilot_attempt(job["id"], status="succeeded", output={**output, "asset_id": asset["id"]}, error=None)
        return asset["id"]

    def _complete_pilot_attempt(self, job_id: UUID, *, status: str, output: dict[str, Any] | None, error):
        with self.database.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM football_brief.video_pilot_attempts WHERE generation_job_id=%s FOR UPDATE",
                (job_id,),
            ).fetchone()
            if not row or row["status"] != "running":
                return
            metrics = dict(row["metrics"] or {})
            if output:
                metrics.update({"provider_request_id": output.get("provider_request_id"), "model_files": output.get("model_files")})
            conn.execute(
                """UPDATE football_brief.video_pilot_attempts SET
                       status=%s,completed_at=now(),wall_clock_ms=%s,gpu_active_ms=%s,
                       peak_vram_mib=%s,average_gpu_temperature_c=%s,peak_gpu_temperature_c=%s,
                       average_gpu_power_w=%s,peak_gpu_power_w=%s,output_asset_id=%s,
                       external_cost_usd=0,failure_code=%s,failure_message=%s,metrics=%s::jsonb
                   WHERE id=%s""",
                (
                    status,
                    output.get("wall_clock_ms") if output else 0,
                    output.get("gpu_active_ms") if output else 0,
                    (output.get("gpu_metrics") or {}).get("peak_vram_mib") if output else None,
                    (output.get("gpu_metrics") or {}).get("average_gpu_temperature_c") if output else None,
                    (output.get("gpu_metrics") or {}).get("peak_gpu_temperature_c") if output else None,
                    (output.get("gpu_metrics") or {}).get("average_gpu_power_w") if output else None,
                    (output.get("gpu_metrics") or {}).get("peak_gpu_power_w") if output else None,
                    output.get("asset_id") if output else None,
                    error[0] if error else None,
                    error[1] if error else None,
                    json.dumps(metrics, sort_keys=True, default=str),
                    row["id"],
                ),
            )

    def _reconcile_completed_once(self) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT j.* FROM football_brief.generation_jobs j
                   JOIN football_brief.local_video_clip_bindings b ON b.generation_job_id=j.id
                   WHERE j.job_type='local_clip' AND j.status='succeeded'
                     AND b.output_asset_id IS NULL AND j.output_payload IS NOT NULL
                   ORDER BY j.finished_at,j.id LIMIT 1"""
            ).fetchone()
        if not row:
            return None
        asset_id = self._register_output(dict(row), dict(row["output_payload"]))
        return {"ok": True, "claimed": False, "reconciled": True, "job_id": str(row["id"]), "asset_id": str(asset_id)}

    def _input_path(self, row) -> Path:
        metadata = dict(row["input_metadata"] or {})
        source_job = metadata.get("generation_job_id")
        if source_job:
            with self.database.connection() as conn:
                job = conn.execute("SELECT output_payload FROM football_brief.generation_jobs WHERE id=%s", (source_job,)).fetchone()
            if job:
                candidate = Path(str((job["output_payload"] or {}).get("storage_path") or "")).resolve()
                if candidate.is_file() and (candidate == self.artifact_root or self.artifact_root in candidate.parents):
                    return candidate
        uri = str(row["input_storage_uri"] or "")
        if not uri.startswith("local-artifact://"):
            raise RuntimeError("P114 currently accepts only local-artifact input assets")
        relative = Path(uri.removeprefix("local-artifact://"))
        for candidate in (self.artifact_root / relative, self.artifact_root / Path(*relative.parts[1:])):
            resolved = candidate.resolve()
            if resolved.is_file() and self.artifact_root in resolved.parents:
                return resolved
        raise RuntimeError("input asset file is unavailable under the local artifact root")

    def _verify_model_files(self, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
        verified: list[dict[str, str]] = []
        for entry in entries:
            relative = Path(str(entry["relative_path"]))
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("model file path escapes the configured ComfyUI root")
            path = (self.comfy_root / relative).resolve()
            if path != self.comfy_root and self.comfy_root not in path.parents:
                raise RuntimeError("model file path escapes the configured ComfyUI root")
            if not path.is_file():
                raise RuntimeError(f"required model file is missing: {relative.as_posix()}")
            actual = self._cached_hash(path)
            if actual != entry["sha256"]:
                raise RuntimeError(f"model file hash mismatch: {relative.as_posix()}")
            verified.append({"role": str(entry["role"]), "relative_path": relative.as_posix(), "sha256": actual})
        return verified

    @staticmethod
    def _repo_file(value: str) -> Path:
        path = Path(value).resolve()
        if path != ROOT and ROOT not in path.parents:
            raise RuntimeError("workflow path escapes the repository")
        if not path.is_file():
            raise RuntimeError("workflow file is missing")
        return path

    def _cached_hash(self, path: Path) -> str:
        stat = path.stat()
        key = (str(path), int(stat.st_size), int(stat.st_mtime_ns))
        if key not in self._hash_cache:
            self._hash_cache = {key: sha256_file(path)}
        return self._hash_cache[key]

    @staticmethod
    def _probe_video(path: Path) -> dict[str, Any]:
        executable = os.getenv("P114_FFPROBE_PATH", "ffprobe")
        if not shutil.which(executable) and not Path(executable).is_file():
            raise RuntimeError("ffprobe is required for local video validation")
        result = subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe rejected local video: {(result.stderr or result.stdout)[-2000:]}")
        data = json.loads(result.stdout)
        streams = data.get("streams") or []
        if not streams:
            raise RuntimeError("local video has no video stream")
        stream = streams[0]
        rate = str(stream.get("avg_frame_rate") or "0/1")
        numerator, denominator = (float(value) for value in rate.split("/", 1))
        fps = numerator / denominator if denominator else 0
        duration = float((data.get("format") or {}).get("duration") or 0)
        if int(stream.get("width") or 0) <= 0 or int(stream.get("height") or 0) <= 0 or fps <= 0 or duration <= 0:
            raise RuntimeError("local video media metadata is invalid")
        return {"width": int(stream["width"]), "height": int(stream["height"]), "fps": fps, "duration_seconds": duration}

    def _job_status(self, job_id: UUID) -> str:
        with self.database.connection() as conn:
            row = conn.execute("SELECT status FROM football_brief.generation_jobs WHERE id=%s", (job_id,)).fetchone()
        return str(row["status"]) if row else "missing"

    def _start_heartbeat(self, job_id, attempt_id, lease_token):
        stop = threading.Event()
        interval = max(10.0, min(60.0, self.lease_seconds / 3))

        def beat() -> None:
            while not stop.wait(interval):
                try:
                    self.jobs.heartbeat(
                        GenerationJobHeartbeat(
                            job_id=job_id,
                            attempt_id=attempt_id,
                            lease_token=lease_token,
                            worker_id=self.worker_id,
                            lease_seconds=self.lease_seconds,
                        )
                    )
                except Exception:
                    return

        thread = threading.Thread(target=beat, name=f"p114-heartbeat-{job_id}", daemon=True)
        thread.start()
        return stop, thread


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the guarded P114 local video worker.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = P114LocalVideoWorker(database)
    try:
        while True:
            result = worker.run_once()
            print(json.dumps(result, default=str, sort_keys=True), flush=True)
            if args.once:
                return 0 if result.get("ok") else 1
            if not result.get("claimed") and not result.get("reconciled"):
                time.sleep(max(args.poll_seconds, 0.5))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
