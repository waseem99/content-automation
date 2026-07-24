from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobType,
)
from src.application.scripts.models import ScriptGenerateRequest
from src.application.scripts.validated_service import ValidatedScriptReviewService
from src.application.visuals.models import CandidateCheck, CandidateCheckStatus, CandidateCheckType, CandidateResult
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.local_pipeline import LocalPipelineService
from src.operations.local_worker import LocalGenerationWorker, _sha256


ALL_SUPPORTED_TYPES = {
    GenerationJobType.SCRIPT,
    GenerationJobType.NARRATION,
    GenerationJobType.KEYFRAME,
    GenerationJobType.PREVIEW,
}


class AlwaysOnLocalGenerationWorker(LocalGenerationWorker):
    """Durable local worker for scripts, narration, keyframes, and MP4 previews."""

    def __init__(
        self,
        database: Database,
        *,
        allowed_job_types: Iterable[GenerationJobType] = ALL_SUPPORTED_TYPES,
    ) -> None:
        super().__init__(database)
        self.scripts = ValidatedScriptReviewService(database)
        self.pipeline = LocalPipelineService(database)
        self.allowed_job_types = frozenset(allowed_job_types)
        if not self.allowed_job_types or not self.allowed_job_types.issubset(ALL_SUPPORTED_TYPES):
            raise ValueError("at least one supported local job type is required")
        self.lease_seconds = int(os.getenv("LOCAL_WORKER_LEASE_SECONDS", "900"))
        self.auto_continue_seconds = max(10, int(os.getenv("LOCAL_AUTO_CONTINUE_SECONDS", "30")))
        self.auto_continue_limit = max(1, min(20, int(os.getenv("LOCAL_AUTO_CONTINUE_LIMIT", "2"))))
        self._next_auto_continue = 0.0
        self._reconcile_after: dict[str, float] = {}

    def run_once(self) -> dict[str, Any]:
        reconciled = self._reconcile_completed_once()
        if reconciled is not None:
            return reconciled

        continued = self._continue_approved_if_due()
        if continued is not None:
            return continued

        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=self.allowed_job_types,
            requested_job_types=self.allowed_job_types,
            providers=(),
            lease_seconds=self.lease_seconds,
        )
        if not claim:
            return {"ok": True, "claimed": False}

        job = claim["job"]
        attempt = claim["attempt"]
        lease_token = claim["lease_token"]
        stop_heartbeat, heartbeat_thread = self._start_heartbeat(
            job_id=job["id"],
            attempt_id=attempt["id"],
            lease_token=lease_token,
        )
        completed = False
        try:
            job_type = GenerationJobType(job["job_type"])
            if job_type == GenerationJobType.SCRIPT:
                output = self._script(job)
            elif job_type == GenerationJobType.NARRATION:
                output = self._narration(job)
            elif job_type == GenerationJobType.KEYFRAME:
                output = self._keyframe(job)
            elif job_type == GenerationJobType.PREVIEW:
                output = self._preview(job)
            else:  # pragma: no cover - guarded by the queue claim
                raise RuntimeError(f"unsupported local job type: {job['job_type']}")

            stop_heartbeat.set()
            heartbeat_thread.join(timeout=5)
            self.jobs.complete(
                GenerationJobCompletion(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    output_payload=output,
                    actual_cost_usd=0,
                    provider_request_id=output.get("provider_request_id"),
                )
            )
            completed = True
            if job_type == GenerationJobType.NARRATION:
                self._register_audio(job=job, output=output)
            elif job_type == GenerationJobType.KEYFRAME:
                self._register_keyframe(job=job, output=output)
            elif job_type == GenerationJobType.PREVIEW:
                self._register_preview(job=job, output=output)
            return {
                "ok": True,
                "claimed": True,
                "job_id": str(job["id"]),
                "job_type": job["job_type"],
                "output": output,
            }
        except Exception as exc:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=5)
            if completed:
                self._reconcile_after[str(job["id"])] = time.monotonic() + 30
                return {
                    "ok": False,
                    "claimed": True,
                    "job_id": str(job["id"]),
                    "job_type": job["job_type"],
                    "registration_pending": job["job_type"]
                    in {
                        GenerationJobType.NARRATION.value,
                        GenerationJobType.KEYFRAME.value,
                        GenerationJobType.PREVIEW.value,
                    },
                    "error": f"{type(exc).__name__}: {exc}",
                }
            self.jobs.fail(
                GenerationJobFailure(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    error_code="local_worker_execution_failed",
                    error_message=f"{type(exc).__name__}: {exc}"[:5000],
                    retryable=isinstance(exc, (TimeoutError, ConnectionError, OSError, subprocess.SubprocessError)),
                    actual_cost_usd=0,
                    error_details={"job_type": job["job_type"], "external_fee_incurred": False},
                )
            )
            return {
                "ok": False,
                "claimed": True,
                "job_id": str(job["id"]),
                "job_type": job["job_type"],
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _script(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = dict(job["input_payload"])
        request = ScriptGenerateRequest.model_validate(payload["request"])
        result = self.scripts.initialize(
            content_id=job["portfolio_content_id"],
            request=request,
            actor=self.worker_id,
        )
        document = result["document"]
        return {
            "kind": "local_ollama_script",
            "script_document_id": str(document["id"]),
            "script_version_id": str(document["current_version_id"]),
            "status": document["current_version_status"],
            "provider": "ollama-local",
            "model_id": request.local_model_id,
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
        }

    def _preview(self, job: dict[str, Any]) -> dict[str, Any]:
        ffmpeg = self._ffmpeg_path()
        payload = dict(job["input_payload"])
        audio_ids = [UUID(value) for value in payload.get("audio_job_ids") or []]
        scenes = sorted(payload.get("scenes") or [], key=lambda item: int(item["sequence"]))
        if not audio_ids or not scenes:
            raise RuntimeError("preview requires selected audio jobs and selected visual scenes")

        output_dir = self.artifact_root / "jobs" / str(job["id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_paths = [self._dependency_path(job_id, expected_kind="local_kokoro_narration") for job_id in audio_ids]
        image_paths = [
            self._dependency_path(UUID(item["generation_job_id"]), expected_kind="local_comfyui_keyframe")
            for item in scenes
        ]

        audio_manifest = output_dir / "audio-concat.txt"
        audio_lines: list[str] = []
        for ordinal, source in enumerate(audio_paths, start=1):
            name = f"audio-{ordinal:03d}{source.suffix.lower() or '.wav'}"
            shutil.copy2(source, output_dir / name)
            audio_lines.append(f"file '{name}'")
        audio_manifest.write_text("\n".join(audio_lines) + "\n", encoding="utf-8")

        scene_manifest = output_dir / "scene-concat.txt"
        scene_lines: list[str] = []
        total_duration = 0.0
        for ordinal, (source, item) in enumerate(zip(image_paths, scenes, strict=True), start=1):
            name = f"scene-{ordinal:03d}{source.suffix.lower() or '.png'}"
            shutil.copy2(source, output_dir / name)
            duration = max(0.25, min(float(item["duration_seconds"]), 3600.0))
            total_duration += duration
            scene_lines.extend((f"file '{name}'", f"duration {duration:.3f}"))
        scene_lines.append(f"file 'scene-{len(image_paths):03d}{image_paths[-1].suffix.lower() or '.png'}'")
        scene_manifest.write_text("\n".join(scene_lines) + "\n", encoding="utf-8")

        narration = output_dir / "narration.wav"
        silent_video = output_dir / "silent-preview.mp4"
        preview = output_dir / "preview.mp4"
        timeout = max(60, int(job.get("timeout_seconds") or 1800))
        self._run_ffmpeg(
            ffmpeg,
            ["-y", "-f", "concat", "-safe", "0", "-i", audio_manifest.name, "-c:a", "pcm_s16le", narration.name],
            cwd=output_dir,
            timeout=timeout,
        )
        width = int(payload.get("width") or 704)
        height = int(payload.get("height") or 1280)
        fps = int(payload.get("fps") or 30)
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
        )
        self._run_ffmpeg(
            ffmpeg,
            [
                "-y", "-f", "concat", "-safe", "0", "-i", scene_manifest.name,
                "-vf", filter_graph, "-r", str(fps), "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "21", "-an", silent_video.name,
            ],
            cwd=output_dir,
            timeout=timeout,
        )
        self._run_ffmpeg(
            ffmpeg,
            [
                "-y", "-i", silent_video.name, "-i", narration.name,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", preview.name,
            ],
            cwd=output_dir,
            timeout=timeout,
        )
        if not preview.is_file() or preview.stat().st_size == 0:
            raise RuntimeError("FFmpeg preview output is missing")
        return {
            "kind": "local_ffmpeg_preview",
            "storage_path": str(preview),
            "storage_uri": f"local-artifact://jobs/{job['id']}/preview.mp4",
            "local_locator": f"content://jobs/{job['id']}/preview.mp4",
            "sha256": _sha256(preview),
            "mime_type": "video/mp4",
            "size_bytes": preview.stat().st_size,
            "width": width,
            "height": height,
            "fps": fps,
            "duration_seconds": round(total_duration, 3),
            "provider": "ffmpeg-local",
            "model_id": job.get("model_id"),
            "audio_job_ids": [str(value) for value in audio_ids],
            "visual_job_ids": [str(item["generation_job_id"]) for item in scenes],
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
        }

    def _asset(self, *, job: dict[str, Any], output: dict[str, Any], asset_type: str) -> UUID:
        """Register verified local model output as rights-approved, not content-approved."""
        with self.database.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM football_brief.assets WHERE sha256=%s",
                (output["sha256"],),
            ).fetchone()
            if existing:
                return existing["id"]
            row = conn.execute(
                """INSERT INTO football_brief.assets
                   (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                    sha256,mime_type,size_bytes,metadata,created_by)
                   VALUES (%s,'ai_generated','approved',%s,%s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING id""",
                (
                    asset_type,
                    Path(output["storage_path"]).name,
                    output["storage_uri"],
                    output["sha256"],
                    output["mime_type"],
                    output["size_bytes"],
                    json.dumps(
                        {
                            "generation_job_id": str(job["id"]),
                            "provider": output.get("provider"),
                            "model_id": output.get("model_id"),
                            "local_only": True,
                            "rights_review": "local_ai_generation_approved_for_internal_review",
                            "human_content_review_required": True,
                        }
                    ),
                    self.worker_id,
                ),
            ).fetchone()
            return row["id"]

    def _register_keyframe(self, *, job: dict[str, Any], output: dict[str, Any]) -> None:
        asset_id = self._asset(job=job, output=output, asset_type="image")
        with self.database.connection() as conn:
            candidate = conn.execute(
                "SELECT id FROM football_brief.visual_candidates WHERE generation_job_id=%s",
                (job["id"],),
            ).fetchone()
        if not candidate:
            raise RuntimeError("visual candidate binding not found")
        automated = {CandidateCheckType.FORMAT, CandidateCheckType.CORRUPTION}
        checks = [
            CandidateCheck(
                check_type=kind,
                status=CandidateCheckStatus.PASS if kind in automated else CandidateCheckStatus.WARNING,
                score=100 if kind in automated else None,
                evidence=(
                    {"verified_by": "local_worker", "sha256": output["sha256"]}
                    if kind in automated
                    else {"status": "pending_human_review", "automatic_approval": False}
                ),
                checked_by=self.worker_id,
            )
            for kind in CandidateCheckType
        ]
        self.visuals.register_candidate_result(
            candidate_id=candidate["id"],
            result=CandidateResult(
                asset_id=asset_id,
                width=output["width"],
                height=output["height"],
                mime_type=output["mime_type"],
                provenance={
                    "generation_job_id": str(job["id"]),
                    "provider_request_id": output.get("provider_request_id"),
                    "provider": output.get("provider"),
                    "model_id": output.get("model_id"),
                    "seed": output.get("seed"),
                    "sha256": output["sha256"],
                    "external_fee_incurred": False,
                },
                checks=checks,
            ),
            actor=self.worker_id,
        )

    def _register_preview(self, *, job: dict[str, Any], output: dict[str, Any]) -> None:
        asset_id = self._asset(job=job, output=output, asset_type="video")
        with self.database.transaction() as conn:
            existing = conn.execute(
                """SELECT id FROM football_brief.portfolio_content_artifacts
                   WHERE portfolio_content_id=%s AND kind='preview' AND local_locator=%s""",
                (job["portfolio_content_id"], output["local_locator"]),
            ).fetchone()
            if existing:
                return
            conn.execute(
                """INSERT INTO football_brief.portfolio_content_artifacts
                   (portfolio_content_id,kind,label,version,local_locator,mime_type,sha256,
                    size_bytes,metadata,created_by)
                   VALUES (%s,'preview',%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (
                    job["portfolio_content_id"],
                    "Local deterministic MP4 preview",
                    int(job["content_version"]),
                    output["local_locator"],
                    output["mime_type"],
                    output["sha256"],
                    output["size_bytes"],
                    json.dumps(
                        {
                            "asset_id": str(asset_id),
                            "generation_job_id": str(job["id"]),
                            "provider": output["provider"],
                            "model_id": output.get("model_id"),
                            "duration_seconds": output["duration_seconds"],
                            "width": output["width"],
                            "height": output["height"],
                            "fps": output["fps"],
                            "external_fee_incurred": False,
                            "human_review_required": True,
                        }
                    ),
                    self.worker_id,
                ),
            )

    def _dependency_path(self, job_id: UUID, *, expected_kind: str) -> Path:
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT status,output_payload FROM football_brief.generation_jobs WHERE id=%s",
                (job_id,),
            ).fetchone()
        if not row or row["status"] != "succeeded":
            raise RuntimeError(f"dependency job {job_id} is not succeeded")
        output = dict(row["output_payload"] or {})
        if output.get("kind") != expected_kind:
            raise RuntimeError(f"dependency job {job_id} has unexpected output kind")
        path = Path(str(output.get("storage_path") or "")).resolve()
        root = self.artifact_root.resolve()
        if not path.is_file() or (path != root and root not in path.parents):
            raise RuntimeError(f"dependency job {job_id} output path is unavailable or unsafe")
        return path

    @staticmethod
    def _run_ffmpeg(executable: str, arguments: list[str], *, cwd: Path, timeout: int) -> None:
        completed = subprocess.run(
            [executable, *arguments],
            cwd=cwd,
            check=False,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout or "ffmpeg failed")[-4000:]
            raise RuntimeError(f"ffmpeg exited with {completed.returncode}: {diagnostic}")

    @staticmethod
    def _ffmpeg_path() -> str:
        configured = os.getenv("LOCAL_FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg"
        if Path(configured).is_file():
            return str(Path(configured).resolve())
        resolved = shutil.which(configured)
        if not resolved:
            raise RuntimeError("FFmpeg is not installed or not on PATH")
        return resolved

    def _start_heartbeat(self, *, job_id, attempt_id, lease_token) -> tuple[threading.Event, threading.Thread]:
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

        thread = threading.Thread(target=beat, name=f"job-heartbeat-{job_id}", daemon=True)
        thread.start()
        return stop, thread

    def _continue_approved_if_due(self) -> dict[str, Any] | None:
        now = time.monotonic()
        if now < self._next_auto_continue:
            return None
        self._next_auto_continue = now + self.auto_continue_seconds
        include_audio = GenerationJobType.NARRATION in self.allowed_job_types
        include_visuals = GenerationJobType.KEYFRAME in self.allowed_job_types
        include_previews = GenerationJobType.PREVIEW in self.allowed_job_types
        if not include_audio and not include_visuals and not include_previews:
            return None
        result = self.pipeline.continue_approved(
            limit=self.auto_continue_limit,
            actor=self.worker_id,
            include_audio=include_audio,
            include_visuals=include_visuals,
            include_previews=include_previews,
        )
        if (
            not result["audio_initialized"]
            and not result["visuals_initialized"]
            and not result["previews_enqueued"]
            and not result["blocked"]
        ):
            return None
        return {"claimed": False, "automatic_continuation": True, **result}

    def _reconcile_completed_once(self) -> dict[str, Any] | None:
        wanted: list[str] = []
        if GenerationJobType.NARRATION in self.allowed_job_types:
            wanted.append(GenerationJobType.NARRATION.value)
        if GenerationJobType.KEYFRAME in self.allowed_job_types:
            wanted.append(GenerationJobType.KEYFRAME.value)
        if GenerationJobType.PREVIEW in self.allowed_job_types:
            wanted.append(GenerationJobType.PREVIEW.value)
        if not wanted:
            return None
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM (
                       SELECT j.*,'narration' AS reconciliation_kind
                       FROM football_brief.generation_jobs j
                       JOIN football_brief.audio_segment_takes ast ON ast.generation_job_id=j.id
                       WHERE j.status='succeeded' AND j.job_type='narration' AND ast.status='queued'
                       UNION ALL
                       SELECT j.*,'keyframe' AS reconciliation_kind
                       FROM football_brief.generation_jobs j
                       JOIN football_brief.visual_candidates vc ON vc.generation_job_id=j.id
                       WHERE j.status='succeeded' AND j.job_type='keyframe' AND vc.status='queued'
                       UNION ALL
                       SELECT j.*,'preview' AS reconciliation_kind
                       FROM football_brief.generation_jobs j
                       WHERE j.status='succeeded' AND j.job_type='preview'
                         AND NOT EXISTS (
                           SELECT 1 FROM football_brief.portfolio_content_artifacts pca
                           WHERE pca.portfolio_content_id=j.portfolio_content_id
                             AND pca.kind='preview'
                             AND pca.local_locator=j.output_payload->>'local_locator'
                         )
                   ) pending
                   WHERE job_type = ANY(%s::text[])
                   ORDER BY queued_at,id LIMIT 20""",
                (wanted,),
            ).fetchall()
        now = time.monotonic()
        selected = next(
            (dict(row) for row in rows if now >= self._reconcile_after.get(str(row["id"]), 0.0)),
            None,
        )
        if selected is None:
            return None
        output = dict(selected.get("output_payload") or {})
        if not output:
            self._reconcile_after[str(selected["id"])] = now + 300
            return {
                "ok": False,
                "claimed": False,
                "reconciliation_job_id": str(selected["id"]),
                "error": "succeeded job has no output payload",
            }
        try:
            if selected["reconciliation_kind"] == "narration":
                self._register_audio(job=selected, output=output)
            elif selected["reconciliation_kind"] == "keyframe":
                self._register_keyframe(job=selected, output=output)
            else:
                self._register_preview(job=selected, output=output)
            self._reconcile_after.pop(str(selected["id"]), None)
            return {
                "ok": True,
                "claimed": False,
                "reconciled": True,
                "job_id": str(selected["id"]),
                "job_type": selected["job_type"],
            }
        except Exception as exc:
            self._reconcile_after[str(selected["id"])] = now + 60
            return {
                "ok": False,
                "claimed": False,
                "reconciled": False,
                "job_id": str(selected["id"]),
                "job_type": selected["job_type"],
                "error": f"{type(exc).__name__}: {exc}",
            }


def _parse_types(raw: str) -> frozenset[GenerationJobType]:
    values = {item.strip() for item in raw.split(",") if item.strip()}
    if not values:
        raise argparse.ArgumentTypeError("at least one job type is required")
    try:
        result = frozenset(GenerationJobType(value) for value in values)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not result.issubset(ALL_SUPPORTED_TYPES):
        allowed = ",".join(sorted(item.value for item in ALL_SUPPORTED_TYPES))
        raise argparse.ArgumentTypeError(f"local worker job types must be a subset of: {allowed}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the always-on local production worker.")
    parser.add_argument("--once", action="store_true", help="Reconcile or claim at most one job.")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument(
        "--job-types",
        type=_parse_types,
        default=frozenset(ALL_SUPPORTED_TYPES),
        help="Comma-separated subset of script,narration,keyframe,preview.",
    )
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = AlwaysOnLocalGenerationWorker(database, allowed_job_types=args.job_types)
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
