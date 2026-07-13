"""File-backed cost, terms, and provenance gates for P68 pilot generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from src.application.budget.metadata_filter import scrub_metadata
from src.p68_job_state import atomic_write_json, utc_now
from src.p68_video_provider import VideoGenerationRequest, VideoJob


LEDGER_VERSION = "p68.generation_ledger.v1"


class SpendDecision(StrEnum):
    ALLOW = "allow"
    NEEDS_APPROVAL = "needs_approval"
    STOP = "stop"


@dataclass(frozen=True)
class GenerationBudget:
    soft_cap_usd: Decimal = Decimal("4.00")
    hard_cap_usd: Decimal = Decimal("10.00")
    rn_gpu_hourly_usd: Decimal = Decimal("0.00")

    def estimate_rn(self, runtime_seconds: Decimal) -> Decimal:
        return (runtime_seconds / Decimal("3600") * self.rn_gpu_hourly_usd).quantize(Decimal("0.0001"))

    def decide(self, *, current_spend_usd: Decimal, estimated_cost_usd: Decimal, premium: bool = False) -> SpendDecision:
        projected = current_spend_usd + estimated_cost_usd
        if projected > self.hard_cap_usd:
            return SpendDecision.STOP
        if premium or projected > self.soft_cap_usd:
            return SpendDecision.NEEDS_APPROVAL
        return SpendDecision.ALLOW


@dataclass(frozen=True)
class TermsEvidence:
    provider: str
    model_id: str
    license_type: str
    license_url: str
    terms_snapshot_sha256: str
    commercial_use_allowed: bool
    modification_allowed: bool
    captured_at: str

    def __post_init__(self) -> None:
        if len(self.terms_snapshot_sha256) != 64:
            raise ValueError("terms_snapshot_sha256 must be a SHA-256 digest")


class GenerationLedger:
    def __init__(self, path: Path, pilot_id: str):
        self.path = path
        self.pilot_id = pilot_id
        if path.is_file():
            self.payload = json.loads(path.read_text(encoding="utf-8"))
            if self.payload.get("schema_version") != LEDGER_VERSION or self.payload.get("pilot_id") != pilot_id:
                raise ValueError(f"Unsupported generation ledger: {path}")
        else:
            self.payload = {
                "schema_version": LEDGER_VERSION,
                "pilot_id": pilot_id,
                "jobs": [],
                "spend_usd": "0.0000",
                "publish_allowed": False,
            }
            self._save()

    @property
    def spend_usd(self) -> Decimal:
        return Decimal(self.payload["spend_usd"])

    @property
    def committed_spend_usd(self) -> Decimal:
        """Actual spend plus estimates still reserved by non-terminal jobs."""
        committed = Decimal("0")
        for item in self.payload["jobs"]:
            actual = item.get("actual_cost_usd")
            if actual is not None:
                committed += Decimal(str(actual))
            elif item.get("status") not in {"failed", "cancelled"}:
                committed += Decimal(str(item.get("estimated_cost_usd") or "0"))
        return committed.quantize(Decimal("0.0001"))

    def _save(self) -> None:
        self.payload["updated_at"] = utc_now()
        atomic_write_json(self.path, self.payload)

    def find(self, idempotency_key: str) -> dict[str, Any] | None:
        return next((item for item in self.payload["jobs"] if item["idempotency_key"] == idempotency_key), None)

    def record_submission(
        self,
        *,
        request: VideoGenerationRequest,
        job: VideoJob,
        terms: TermsEvidence,
        estimated_cost_usd: Decimal,
        budget_decision: SpendDecision,
    ) -> dict[str, Any]:
        existing = self.find(request.idempotency_key)
        if existing:
            return existing
        if budget_decision != SpendDecision.ALLOW:
            raise PermissionError(f"Generation blocked by budget decision: {budget_decision.value}")
        prompt_hash = hashlib.sha256(request.prompt.encode()).hexdigest()
        record = {
            "pilot_id": request.pilot_id,
            "shot_id": request.shot_id,
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "model_id": request.model_id,
            "idempotency_key": request.idempotency_key,
            "input_path": str(request.input_image),
            "input_sha256": request.input_sha256,
            "prompt_hash": prompt_hash,
            "seed": request.seed,
            "frame_count": request.frame_count,
            "status": job.status.value,
            "estimated_cost_usd": str(estimated_cost_usd.quantize(Decimal("0.0001"))),
            "actual_cost_usd": None,
            "terms": asdict(terms),
            "metadata": scrub_metadata(request.metadata),
            "submitted_at": job.submitted_at,
            "publish_allowed": False,
        }
        self.payload["jobs"].append(record)
        self._save()
        return record

    def record_completion(self, *, idempotency_key: str, output_path: Path, actual_cost_usd: Decimal) -> dict[str, Any]:
        record = self.find(idempotency_key)
        if record is None:
            raise KeyError(idempotency_key)
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        record.update(
            {
                "status": "succeeded",
                "output_path": str(output_path),
                "output_sha256": digest,
                "actual_cost_usd": str(actual_cost_usd.quantize(Decimal("0.0001"))),
                "completed_at": utc_now(),
            }
        )
        self.payload["spend_usd"] = str(
            sum((Decimal(str(item.get("actual_cost_usd") or "0")) for item in self.payload["jobs"]), Decimal("0"))
            .quantize(Decimal("0.0001"))
        )
        self._save()
        return record

    def record_job_status(self, job: VideoJob) -> dict[str, Any]:
        record = self.find(job.idempotency_key)
        if record is None:
            raise KeyError(job.idempotency_key)
        record["status"] = job.status.value
        record["last_polled_at"] = utc_now()
        if job.output_descriptor:
            record["output_descriptor"] = scrub_metadata(job.output_descriptor)
        if job.error:
            record["error"] = job.error[-2000:]
        self._save()
        return record
