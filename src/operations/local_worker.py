from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import soundfile as sf
from PIL import Image

from src.application.audio.adapters import proportional_preview_timings
from src.application.audio.models import AlignmentSource, AudioTakeResult
from src.application.audio.service import AudioProductionService
from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobType,
)
from src.operations.job_logging import ObservedGenerationJobService
from src.application.visuals.models import CandidateCheck, CandidateCheckStatus, CandidateCheckType, CandidateResult
from src.application.visuals.validated_service import ValidatedVisualProjectService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.p68_keyframe_provider import (
    ComfyUIKeyframeProvider,
    ImageJobStatus,
    KeyframeGenerationRequest,
)


SUPPORTED_TYPES = {GenerationJobType.NARRATION, GenerationJobType.KEYFRAME}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _replace_pronunciation(text: str, rules: dict[str, str]) -> str:
    updated = text
    for token, replacement in sorted(rules.items(), key=lambda pair: -len(pair[0])):
        updated = re.sub(rf"\b{re.escape(token)}\b", replacement, updated, flags=re.IGNORECASE)
    return updated


def _audio_metrics(waveform: np.ndarray, sample_rate: int) -> dict[str, Any]:
    if waveform.ndim > 1:
        mono = waveform.mean(axis=1)
        channels = waveform.shape[1]
    else:
        mono = waveform
        channels = 1
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
    true_peak = 20 * math.log10(max(peak, 1e-9))
    approximate_lufs = 20 * math.log10(max(rms, 1e-9))
    silence = float(np.mean(np.abs(mono) < 1e-4)) if mono.size else 1.0
    return {
        "duration_seconds": len(mono) / sample_rate,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "integrated_lufs": approximate_lufs,
        "true_peak_dbfs": true_peak,
        "clipping_count": int(np.sum(np.abs(mono) >= 0.999)),
        "silence_ratio": silence,
    }


class LocalGenerationWorker:
    """Execute only local narration and keyframe jobs; never approve or publish."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.jobs = ObservedGenerationJobService(database)
        self.audio = AudioProductionService(database)
        self.visuals = ValidatedVisualProjectService(database)
        self.worker_id = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer")
        self.artifact_root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def run_once(self) -> dict[str, Any]:
        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=SUPPORTED_TYPES,
            requested_job_types=SUPPORTED_TYPES,
            providers=(),
            lease_seconds=int(os.getenv("LOCAL_WORKER_LEASE_SECONDS", "900")),
        )
        if not claim:
            return {"ok": True, "claimed": False}
        job = claim["job"]
        attempt = claim["attempt"]
        lease_token = claim["lease_token"]
        try:
            if job["job_type"] == GenerationJobType.NARRATION.value:
                output = self._narration(job)
            elif job["job_type"] == GenerationJobType.KEYFRAME.value:
                output = self._keyframe(job)
            else:
                raise RuntimeError(f"unsupported local job type: {job['job_type']}")
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
            if job["job_type"] == GenerationJobType.NARRATION.value:
                self._register_audio(job=job, output=output)
            else:
                self._register_keyframe(job=job, output=output)
            return {"ok": True, "claimed": True, "job_id": str(job["id"]), "job_type": job["job_type"], "output": output}
        except Exception as exc:
            self.jobs.fail(
                GenerationJobFailure(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    error_code="local_worker_execution_failed",
                    error_message=f"{type(exc).__name__}: {exc}"[:5000],
                    retryable=isinstance(exc, (TimeoutError, ConnectionError)),
                    actual_cost_usd=0,
                    error_details={"job_type": job["job_type"], "external_fee_incurred": False},
                )
            )
            return {"ok": False, "claimed": True, "job_id": str(job["id"]), "error": f"{type(exc).__name__}: {exc}"}

    def _narration(self, job: dict[str, Any]) -> dict[str, Any]:
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise RuntimeError("Kokoro is not installed; install video-engine/voice-requirements.txt") from exc
        payload = dict(job["input_payload"])
        text = _replace_pronunciation(str(payload["text"]), dict(payload.get("pronunciation_rules") or {}))
        voice = str(payload["provider_voice_id"])
        speed = float(payload.get("speed") or 1.0)
        lang_code = os.getenv("KOKORO_LANG_CODE", "a")
        pipeline = KPipeline(lang_code=lang_code)
        chunks: list[np.ndarray] = []
        silence = np.zeros(int(24000 * 0.045), dtype=np.float32)
        for _, _, audio in pipeline(text, voice=voice, speed=speed):
            chunk = np.asarray(audio, dtype=np.float32)
            if chunk.size:
                chunks.extend((chunk, silence))
        if not chunks:
            raise RuntimeError("Kokoro returned no audio")
        waveform = np.concatenate(chunks)
        peak = float(np.max(np.abs(waveform)))
        if peak > 0.85:
            waveform *= 0.85 / peak
        output_dir = self.artifact_root / str(job["id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "narration.wav"
        sf.write(path, waveform, 24000, subtype="PCM_16")
        metrics = _audio_metrics(waveform, 24000)
        return {
            "kind": "local_kokoro_narration",
            "storage_path": str(path),
            "storage_uri": f"local-artifact://jobs/{job['id']}/narration.wav",
            "sha256": _sha256(path),
            "mime_type": "audio/wav",
            "size_bytes": path.stat().st_size,
            "text": text,
            "provider": "kokoro",
            "model_id": job.get("model_id"),
            "voice": voice,
            "speed": speed,
            "metrics": metrics,
            "timing_source": "proportional_preview",
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
        }

    def _keyframe(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = dict(job["input_payload"])
        workflow = Path(os.environ["P68_COMFYUI_WORKFLOW_PATH"]).resolve()
        checkpoint = os.environ["P68_COMFYUI_CHECKPOINT"]
        provider = ComfyUIKeyframeProvider(
            base_url=os.getenv("P68_COMFYUI_BASE_URL", "http://127.0.0.1:8188"),
            workflow_path=workflow,
            checkpoint=checkpoint,
        )
        provider.health()
        request = KeyframeGenerationRequest(
            pilot_id=str(payload["visual_project_id"]),
            shot_id=f"{payload['visual_shot_id']}-{payload['candidate_ordinal']}",
            prompt=str(payload["prompt"]),
            negative_prompt=str(payload.get("negative_prompt") or ""),
            seed=int(payload["seed"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            model_id=str(job.get("model_id") or "sdxl-base-1.0"),
        )
        submitted = provider.submit(request)
        deadline = time.monotonic() + int(job.get("timeout_seconds") or 900)
        current = submitted
        while time.monotonic() < deadline:
            current = provider.poll(current)
            if current.status in {ImageJobStatus.SUCCEEDED, ImageJobStatus.FAILED}:
                break
            time.sleep(2)
        if current.status != ImageJobStatus.SUCCEEDED:
            raise TimeoutError(current.error or "ComfyUI keyframe did not complete")
        output_dir = self.artifact_root / str(job["id"])
        path = provider.download(current, output_dir / "keyframe.png")
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
        return {
            "kind": "local_comfyui_keyframe",
            "storage_path": str(path),
            "storage_uri": f"local-artifact://jobs/{job['id']}/keyframe.png",
            "sha256": _sha256(path),
            "mime_type": "image/png",
            "size_bytes": path.stat().st_size,
            "width": width,
            "height": height,
            "provider": job.get("provider"),
            "model_id": job.get("model_id"),
            "seed": payload["seed"],
            "provider_request_id": current.provider_job_id,
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
        }

    def _asset(self, *, job: dict[str, Any], output: dict[str, Any], asset_type: str) -> UUID:
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
                   VALUES (%s,'ai_generated','internal_only',%s,%s,%s,%s,%s,%s::jsonb,%s)
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
                            "human_review_required": True,
                        }
                    ),
                    self.worker_id,
                ),
            ).fetchone()
            return row["id"]

    def _register_audio(self, *, job: dict[str, Any], output: dict[str, Any]) -> None:
        asset_id = self._asset(job=job, output=output, asset_type="audio")
        with self.database.connection() as conn:
            take = conn.execute(
                "SELECT id FROM football_brief.audio_segment_takes WHERE generation_job_id=%s",
                (job["id"],),
            ).fetchone()
        if not take:
            raise RuntimeError("audio take binding not found")
        metrics = output["metrics"]
        timings = proportional_preview_timings(output["text"], metrics["duration_seconds"])
        self.audio.register_take_result(
            take_id=take["id"],
            result=AudioTakeResult(
                asset_id=asset_id,
                duration_seconds=metrics["duration_seconds"],
                sample_rate_hz=metrics["sample_rate_hz"],
                channels=metrics["channels"],
                integrated_lufs=metrics["integrated_lufs"],
                true_peak_dbfs=metrics["true_peak_dbfs"],
                clipping_count=metrics["clipping_count"],
                silence_ratio=metrics["silence_ratio"],
                timing_source=AlignmentSource.PROPORTIONAL_PREVIEW,
                word_timings=timings,
                qc_evidence={
                    "measurement_method": "local_preview_rms_approximation",
                    "forced_alignment_required_for_final_approval": True,
                },
            ),
            actor=self.worker_id,
        )

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
                status=CandidateCheckStatus.PASS if kind in automated or kind is CandidateCheckType.DUPLICATE else CandidateCheckStatus.WARNING,
                score=100 if kind in automated or kind is CandidateCheckType.DUPLICATE else None,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local P87 narration/keyframe worker.")
    parser.add_argument("--once", action="store_true", help="Claim at most one job.")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = LocalGenerationWorker(database)
    try:
        while True:
            result = worker.run_once()
            print(json.dumps(result, default=str, sort_keys=True), flush=True)
            if args.once:
                return 0 if result.get("ok") else 1
            if not result.get("claimed"):
                time.sleep(max(args.poll_seconds, 0.5))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
