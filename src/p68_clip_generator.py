"""Short-running submit/refresh controller for asynchronous P68 video jobs."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.p68_generation_governance import (
    GenerationBudget,
    GenerationLedger,
    SpendDecision,
    TermsEvidence,
)
from src.p68_job_state import atomic_write_json, utc_now
from src.p68_video_provider import VideoGenerationRequest, VideoJob, VideoJobStatus, VideoProvider


GENERATOR_VERSION = "p68.clip_generation.v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed(pilot_id: str, shot_id: str, variant: int) -> int:
    digest = hashlib.sha256(f"{pilot_id}:{shot_id}:{variant}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def load_terms(model_manifest_path: Path) -> TermsEvidence:
    manifest = _load(model_manifest_path)
    license_data = manifest["license"]
    snapshot = license_data.get("terms_snapshot_sha256")
    if not snapshot:
        # Development generation may proceed, but the recorded status remains
        # pending and downstream publication stays blocked. Hashing the manifest
        # makes the exact pending evidence version auditable.
        snapshot = hashlib.sha256(model_manifest_path.read_bytes()).hexdigest()
    return TermsEvidence(
        provider="rn-comfyui-wan",
        model_id=manifest["model_id"],
        license_type=license_data["type"],
        license_url=license_data["url"],
        terms_snapshot_sha256=snapshot,
        commercial_use_allowed=bool(license_data.get("commercial_use_allowed")),
        modification_allowed=bool(license_data.get("modification_allowed")),
        captured_at=utc_now(),
    )


def build_requests(
    pilot_dir: Path,
    artifact_dir: Path,
    *,
    variants: int = 2,
    hero_variants: int | None = None,
    allow_master_preview: bool = False,
    shot_ids: set[str] | None = None,
    skip_authored_science: bool = True,
) -> list[VideoGenerationRequest]:
    if variants < 1:
        raise ValueError("variants must be at least one")
    if hero_variants is not None and hero_variants < variants:
        raise ValueError("hero_variants cannot be lower than standard variants")
    plan = _load(pilot_dir / "content-plan.json")
    prompts = {item["shot_id"]: item for item in _load(pilot_dir / "clip-prompts.json")}
    assets = _load(artifact_dir / "assets" / "asset-manifest.json")
    assets_by_id = {item["shot_id"]: item for item in assets["assets"]}
    requests: list[VideoGenerationRequest] = []
    if skip_authored_science:
        from src.p68_scientific_animation import RENDERERS

        science_ids = {shot_id for candidate_pilot, shot_id in RENDERERS if candidate_pilot == plan["pilot_id"]}
    else:
        science_ids = set()
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        if shot_ids is not None and shot_id not in shot_ids:
            continue
        if shot_id in science_ids:
            continue
        asset = assets_by_id[shot_id]
        if asset["source"] == "continuity_master_preview_fallback" and not allow_master_preview:
            raise ValueError(f"{shot_id} requires a shot-specific keyframe before real clip generation")
        if asset.get("quality_status") == "pending_keyframe_review":
            raise ValueError(f"{shot_id} keyframe requires explicit human approval before generation")
        prompt = prompts[shot_id]
        duration = float(shot["duration_seconds"]) + float(shot.get("transition_handle_seconds") or 0.5)
        variant_count = hero_variants if hero_variants is not None and shot["story_stage"] in {"hook", "reveal"} else variants
        for variant in range(1, variant_count + 1):
            requests.append(
                VideoGenerationRequest(
                    pilot_id=plan["pilot_id"],
                    shot_id=shot_id,
                    input_image=Path(asset["path"]),
                    prompt=(
                        f"{prompt['prompt']} Motion must begin immediately and remain natural. "
                        f"Entry action: {prompt['entry_action']} Exit action: {prompt['exit_action']} "
                        "Preserve subject identity, anatomy, lighting, environment, and screen direction exactly."
                    ),
                    negative_prompt=(
                        f"{prompt['negative_prompt']}, static frame, frozen subject, morphing identity, anatomy drift, "
                        "camera shake, jump cut, duplicate subject, text, logo, watermark"
                    ),
                    duration_seconds=duration,
                    seed=_seed(plan["pilot_id"], shot_id, variant),
                    output_prefix=f"p68/{plan['pilot_id']}/v{variant}",
                    metadata={
                        "variant": variant,
                        "source": asset["source"],
                        "rights_status": asset["rights_status"],
                        "quality_status": asset["quality_status"],
                        "engagement_priority": "hero" if shot["story_stage"] in {"hook", "reveal"} else "standard",
                    },
                )
            )
    return requests


class ClipGenerationController:
    def __init__(
        self,
        *,
        pilot_dir: Path,
        artifact_dir: Path,
        provider: VideoProvider,
        budget: GenerationBudget,
        terms: TermsEvidence,
    ) -> None:
        self.pilot_dir = pilot_dir
        self.artifact_dir = artifact_dir
        self.provider = provider
        self.budget = budget
        self.terms = terms
        self.ledger = GenerationLedger(artifact_dir / "generation" / "generation-ledger.json", pilot_dir.name)

    def submit_missing(
        self,
        requests: list[VideoGenerationRequest],
        *,
        expected_runtime_seconds: Decimal = Decimal("540"),
    ) -> dict[str, Any]:
        estimate = self.budget.estimate_rn(expected_runtime_seconds)
        submitted, cached, blocked = [], [], []
        for request in requests:
            existing = self.ledger.find(request.idempotency_key)
            if existing:
                cached.append({"shot_id": request.shot_id, "idempotency_key": request.idempotency_key})
                continue
            decision = self.budget.decide(
                current_spend_usd=self.ledger.committed_spend_usd,
                estimated_cost_usd=estimate,
                premium=getattr(self.provider, "requires_paid_approval", True),
            )
            if decision != SpendDecision.ALLOW:
                blocked.append({"shot_id": request.shot_id, "decision": decision.value})
                continue
            job = self.provider.submit(request)
            self.ledger.record_submission(
                request=request,
                job=job,
                terms=self.terms,
                estimated_cost_usd=estimate,
                budget_decision=decision,
            )
            submitted.append({"shot_id": request.shot_id, "provider_job_id": job.provider_job_id})
        return {"submitted": submitted, "cached": cached, "blocked": blocked, "publish_allowed": False}

    def refresh(self) -> dict[str, Any]:
        changed, pending, failed = [], [], []
        for record in list(self.ledger.payload["jobs"]):
            if record["status"] in {
                VideoJobStatus.SUCCEEDED.value,
                VideoJobStatus.FAILED.value,
                VideoJobStatus.CANCELLED.value,
            }:
                continue
            job = VideoJob(
                provider=record["provider"],
                provider_job_id=record["provider_job_id"],
                idempotency_key=record["idempotency_key"],
                status=VideoJobStatus(record["status"]),
                submitted_at=record["submitted_at"],
                model_id=record["model_id"],
                output_descriptor=record.get("output_descriptor"),
                error=record.get("error"),
            )
            polled = self.provider.poll(job)
            if polled.status == VideoJobStatus.SUCCEEDED:
                variant = int(record.get("metadata", {}).get("variant") or 1)
                output = self.provider.download(
                    polled,
                    self.artifact_dir / "clips" / "generated" / f"{record['shot_id']}-v{variant}",
                )
                self.ledger.record_completion(
                    idempotency_key=record["idempotency_key"],
                    output_path=output,
                    actual_cost_usd=Decimal(record["estimated_cost_usd"]),
                )
                changed.append({"shot_id": record["shot_id"], "output_path": str(output)})
            elif polled.status == VideoJobStatus.FAILED:
                self.ledger.record_job_status(polled)
                failed.append({"shot_id": record["shot_id"], "error": polled.error})
            else:
                self.ledger.record_job_status(polled)
                pending.append({"shot_id": record["shot_id"], "status": polled.status.value})
        candidates = self.write_candidate_manifest()
        return {
            "completed": changed,
            "pending": pending,
            "failed": failed,
            "candidate_manifest": candidates,
            "publish_allowed": False,
        }

    def write_candidate_manifest(self) -> str:
        candidates = []
        for record in self.ledger.payload["jobs"]:
            if record["status"] != VideoJobStatus.SUCCEEDED.value or not record.get("output_path"):
                continue
            candidates.append(
                {
                    "shot_id": record["shot_id"],
                    "variant": record.get("metadata", {}).get("variant"),
                    "path": record["output_path"],
                    "provider": record["provider"],
                    "provider_job_id": record["provider_job_id"],
                    "model_id": record["model_id"],
                    "prompt_or_asset_reference": f"prompt_sha256:{record['prompt_hash']}",
                    "input_sha256": record["input_sha256"],
                    "output_sha256": record["output_sha256"],
                    "prompt_hash": record["prompt_hash"],
                    "seed": record["seed"],
                    "rights_status": "generated_for_project",
                    "human_review_status": "pending_final_review",
                    "preview_only": True,
                }
            )
        payload = {
            "schema_version": GENERATOR_VERSION,
            "pilot_id": self.pilot_dir.name,
            "candidates": candidates,
            "selected_clips": [],
            "selection_required": True,
            "publish_allowed": False,
        }
        path = self.artifact_dir / "clips" / "generated" / "candidate-manifest.json"
        atomic_write_json(path, payload)
        return str(path)

    def status(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in VideoJobStatus}
        for record in self.ledger.payload["jobs"]:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        return {
            "pilot_id": self.pilot_dir.name,
            "counts": counts,
            "spend_usd": str(self.ledger.spend_usd),
            "committed_spend_usd": str(self.ledger.committed_spend_usd),
            "soft_cap_usd": str(self.budget.soft_cap_usd),
            "hard_cap_usd": str(self.budget.hard_cap_usd),
            "candidate_manifest": str(self.artifact_dir / "clips" / "generated" / "candidate-manifest.json"),
            "publish_allowed": False,
        }
