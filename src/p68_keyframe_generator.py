"""Resumable, bounded controller for P68 keyframe generation."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.p68_job_state import atomic_write_json, utc_now
from src.p68_keyframe_batch import build_keyframe_work_orders, intake_keyframe
from src.p68_keyframe_provider import ImageJob, ImageJobStatus, KeyframeGenerationRequest, KeyframeProvider


LEDGER_VERSION = "p68.keyframe_generation_ledger.v1"


def _seed(pilot_id: str, shot_id: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{pilot_id}:{shot_id}:keyframe-v1".encode()).digest()[:8], "big") % (2**63 - 1)


def build_keyframe_requests(pilots_root: Path, artifact_root: Path, *, pilot_id: str | None = None, shot_ids: set[str] | None = None) -> list[KeyframeGenerationRequest]:
    orders = build_keyframe_work_orders(pilots_root, artifact_root)
    requests = []
    for pilot in orders["pilots"]:
        if pilot_id and pilot["pilot_id"] != pilot_id:
            continue
        for order in pilot["orders"]:
            if shot_ids is not None and order["shot_id"] not in shot_ids:
                continue
            if order["ready_for_video_generation"]:
                continue
            requests.append(KeyframeGenerationRequest(
                pilot_id=order["pilot_id"], shot_id=order["shot_id"],
                prompt=order["still_image_prompt"], negative_prompt=order["negative_prompt"],
                seed=_seed(order["pilot_id"], order["shot_id"]),
            ))
    return requests


class KeyframeGenerationController:
    def __init__(self, *, pilots_root: Path, artifact_root: Path, provider: KeyframeProvider, checkpoint: str, license_type: str, license_url: str, gpu_hourly_usd: Decimal, soft_cap_usd: Decimal, hard_cap_usd: Decimal) -> None:
        if not checkpoint or not license_type or not license_url:
            raise ValueError("checkpoint and model license evidence are required")
        if min(gpu_hourly_usd, soft_cap_usd, hard_cap_usd) < 0 or soft_cap_usd > hard_cap_usd:
            raise ValueError("invalid generation budget")
        self.pilots_root, self.artifact_root, self.provider = pilots_root, artifact_root, provider
        self.checkpoint, self.license_type, self.license_url = checkpoint, license_type, license_url
        self.gpu_hourly_usd, self.soft_cap_usd, self.hard_cap_usd = gpu_hourly_usd, soft_cap_usd, hard_cap_usd
        self.path = artifact_root / "keyframe-generation-ledger.json"
        self.payload = json.loads(self.path.read_text()) if self.path.is_file() else {
            "schema_version": LEDGER_VERSION, "jobs": [], "actual_spend_usd": "0.0000", "publish_allowed": False,
        }
        if self.payload.get("schema_version") != LEDGER_VERSION:
            raise ValueError("unsupported keyframe generation ledger")

    def _save(self) -> None:
        self.payload["updated_at"] = utc_now()
        atomic_write_json(self.path, self.payload)

    def _find(self, key: str) -> dict[str, Any] | None:
        return next((item for item in self.payload["jobs"] if item["idempotency_key"] == key), None)

    @property
    def committed(self) -> Decimal:
        return sum((Decimal(str(item.get("actual_cost_usd") or item.get("estimated_cost_usd") or "0")) for item in self.payload["jobs"] if item["status"] not in {"failed", "cancelled"}), Decimal("0"))

    def estimate(self, runtime_seconds: Decimal) -> Decimal:
        return (runtime_seconds / Decimal("3600") * self.gpu_hourly_usd).quantize(Decimal("0.0001"))

    def submit_missing(self, requests: list[KeyframeGenerationRequest], *, limit: int = 3, expected_runtime_seconds: Decimal = Decimal("120")) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("limit must be positive")
        estimate = self.estimate(expected_runtime_seconds)
        submitted, cached, blocked = [], [], []
        for request in requests:
            if len(submitted) >= limit:
                blocked.append({"pilot_id": request.pilot_id, "shot_id": request.shot_id, "reason": "bounded_batch_limit"})
                continue
            if self._find(request.idempotency_key):
                cached.append({"pilot_id": request.pilot_id, "shot_id": request.shot_id})
                continue
            projected = self.committed + estimate
            if projected > self.hard_cap_usd:
                blocked.append({"pilot_id": request.pilot_id, "shot_id": request.shot_id, "reason": "hard_cap"})
                continue
            if projected > self.soft_cap_usd:
                blocked.append({"pilot_id": request.pilot_id, "shot_id": request.shot_id, "reason": "human_spend_approval_required"})
                continue
            job = self.provider.submit(request)
            self.payload["jobs"].append({
                "pilot_id": request.pilot_id, "shot_id": request.shot_id,
                "provider": job.provider, "provider_job_id": job.provider_job_id,
                "idempotency_key": request.idempotency_key, "status": job.status.value,
                "model_id": request.model_id, "checkpoint": self.checkpoint,
                "prompt_sha256": hashlib.sha256(request.prompt.encode()).hexdigest(), "seed": request.seed,
                "estimated_cost_usd": str(estimate), "actual_cost_usd": None,
                "license": {"type": self.license_type, "url": self.license_url},
                "submitted_at": job.submitted_at, "publish_allowed": False,
            })
            self._save()
            submitted.append({"pilot_id": request.pilot_id, "shot_id": request.shot_id, "provider_job_id": job.provider_job_id})
        return {"submitted": submitted, "cached": cached, "blocked": blocked, "publish_allowed": False}

    def refresh(self) -> dict[str, Any]:
        completed, pending, failed = [], [], []
        for record in self.payload["jobs"]:
            if record["status"] in {"succeeded", "failed", "cancelled"}:
                continue
            job = ImageJob(
                record["provider"], record["provider_job_id"], record["idempotency_key"],
                ImageJobStatus(record["status"]), record["submitted_at"], record["model_id"],
            )
            polled = self.provider.poll(job)
            if polled.status == ImageJobStatus.SUCCEEDED:
                raw = self.provider.download(polled, self.artifact_root / "keyframe-downloads" / record["pilot_id"] / f"{record['shot_id']}.png")
                intake = intake_keyframe(
                    pilots_root=self.pilots_root, artifact_root=self.artifact_root,
                    pilot_id=record["pilot_id"], shot_id=record["shot_id"], source_path=raw,
                    source_kind="generated_original", provider=record["provider"],
                    model_or_collection=record["checkpoint"],
                    rights_evidence=f"Generated for this project under {record['license']['type']}: {record['license']['url']}",
                )
                record.update({"status": "succeeded", "output_sha256": intake["normalized_sha256"], "intake_path": intake["normalized_path"], "actual_cost_usd": record["estimated_cost_usd"], "completed_at": utc_now()})
                completed.append({"pilot_id": record["pilot_id"], "shot_id": record["shot_id"], "human_review_status": "pending_keyframe_review"})
            elif polled.status == ImageJobStatus.FAILED:
                record.update({"status": "failed", "error": polled.error})
                failed.append({"pilot_id": record["pilot_id"], "shot_id": record["shot_id"], "error": polled.error})
            else:
                record["status"] = polled.status.value
                pending.append({"pilot_id": record["pilot_id"], "shot_id": record["shot_id"], "status": polled.status.value})
            self._save()
        self.payload["actual_spend_usd"] = str(sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in self.payload["jobs"]), Decimal("0")).quantize(Decimal("0.0001")))
        self._save()
        return {"completed": completed, "pending": pending, "failed": failed, "human_review_required": True, "publish_allowed": False}

    def status(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in ImageJobStatus}
        for item in self.payload["jobs"]:
            counts[item["status"]] += 1
        return {"counts": counts, "committed_spend_usd": str(self.committed.quantize(Decimal("0.0001"))), "ledger_path": str(self.path), "human_review_required": True, "publish_allowed": False}
