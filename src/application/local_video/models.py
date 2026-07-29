from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID


class LocalVideoJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class LocalVideoRequest:
    generation_job_id: UUID
    generation_attempt_id: UUID
    pilot_case_id: UUID | None
    provider_key: str
    model_key: str
    workflow_key: str
    workflow_path: Path
    workflow_sha256: str
    checkpoint_sha256: str
    input_image_path: Path
    end_image_path: Path | None
    prompt: str
    negative_prompt: str
    seed: int
    width: int
    height: int
    fps: int
    frame_count: int
    inference_steps: int
    output_prefix: str

    def __post_init__(self) -> None:
        if self.provider_key not in {"wan-ai", "tencent-hunyuan"}:
            raise ValueError("unsupported local video provider")
        if not self.workflow_path.is_file():
            raise FileNotFoundError(self.workflow_path)
        if not self.input_image_path.is_file():
            raise FileNotFoundError(self.input_image_path)
        if self.end_image_path is not None and not self.end_image_path.is_file():
            raise FileNotFoundError(self.end_image_path)
        for value, label in (
            (self.workflow_sha256, "workflow_sha256"),
            (self.checkpoint_sha256, "checkpoint_sha256"),
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"{label} must be lowercase SHA-256")
        if not self.prompt.strip():
            raise ValueError("prompt is required")
        if not 256 <= self.width <= 8192 or not 256 <= self.height <= 8192:
            raise ValueError("invalid output resolution")
        if not 1 <= self.fps <= 120:
            raise ValueError("invalid fps")
        if not 1 <= self.frame_count <= 10000:
            raise ValueError("invalid frame count")
        if not 1 <= self.inference_steps <= 500:
            raise ValueError("invalid inference steps")

    @property
    def idempotency_key(self) -> str:
        document = {
            "generation_job_id": str(self.generation_job_id),
            "generation_attempt_id": str(self.generation_attempt_id),
            "pilot_case_id": str(self.pilot_case_id) if self.pilot_case_id else None,
            "provider_key": self.provider_key,
            "model_key": self.model_key,
            "workflow_key": self.workflow_key,
            "workflow_sha256": self.workflow_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "input_image_sha256": _sha256(self.input_image_path),
            "end_image_sha256": _sha256(self.end_image_path) if self.end_image_path else None,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "inference_steps": self.inference_steps,
            "output_prefix": self.output_prefix,
        }
        return hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class LocalVideoJob:
    provider: str
    provider_job_id: str
    idempotency_key: str
    status: LocalVideoJobStatus
    model_key: str
    workflow_sha256: str
    submitted_at: str
    output_descriptor: dict[str, Any] | None = None
    error: str | None = None


def _sha256(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
