from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CompiledVisualPrompt:
    prompt: str
    negative_prompt: str
    components: dict[str, Any]
    reference_snapshot: list[dict[str, Any]]


class VisualPromptCompiler:
    required_components = (
        "subject",
        "action",
        "environment",
        "camera",
        "lighting",
        "palette",
        "framing",
        "exclusions",
    )

    def compile(
        self,
        *,
        scene: dict[str, Any],
        preset: dict[str, Any],
        references: list[dict[str, Any]],
        prompt_patch: dict[str, Any] | None = None,
        negative_prompt_append: str = "",
    ) -> CompiledVisualPrompt:
        patch = dict(prompt_patch or {})
        components: dict[str, Any] = {
            "subject": patch.get("subject", preset.get("subject_rules") or {}),
            "action": patch.get("action", scene.get("visual_brief") or scene.get("narration_text") or ""),
            "environment": patch.get("environment", preset.get("environment_rules") or {}),
            "camera": patch.get("camera", preset.get("camera_rules") or {}),
            "lighting": patch.get("lighting", preset.get("lighting_rules") or {}),
            "palette": patch.get("palette", preset.get("palette") or {}),
            "framing": patch.get("framing", preset.get("framing_rules") or {}),
            "exclusions": patch.get("exclusions", list(preset.get("exclusions") or [])),
        }
        missing = [key for key in self.required_components if key not in components]
        if missing:
            raise ValueError(f"visual prompt components missing: {', '.join(missing)}")
        reference_snapshot = [
            {
                "id": str(item["id"]),
                "reference_key": item["reference_key"],
                "reference_type": item["reference_type"],
                "asset_id": str(item["asset_id"]) if item.get("asset_id") else None,
                "reference_fingerprint": item["reference_fingerprint"],
                "description": item["description"],
                "attributes": dict(item.get("attributes") or {}),
            }
            for item in sorted(references, key=lambda row: (row["reference_type"], row["reference_key"]))
            if item.get("active", True)
        ]
        component_lines = [
            f"{name}: {self._display(value)}"
            for name, value in components.items()
            if name != "exclusions"
        ]
        if reference_snapshot:
            component_lines.append(
                "continuity references: "
                + "; ".join(
                    f"{item['reference_type']}={item['description']}"
                    for item in reference_snapshot
                )
            )
        prompt = ". ".join(line for line in component_lines if line.strip())
        standard_negative = [
            "text",
            "watermark",
            "logo",
            "signature",
            "caption",
            "UI overlay",
            "corruption",
            "duplicate subject",
            "cropped landmark",
            "inconsistent lighting",
        ]
        negatives = [
            str(preset.get("negative_prompt") or "").strip(),
            ", ".join(str(item) for item in components["exclusions"]),
            ", ".join(standard_negative),
            negative_prompt_append.strip(),
        ]
        return CompiledVisualPrompt(
            prompt=prompt,
            negative_prompt=", ".join(item for item in negatives if item),
            components=components,
            reference_snapshot=reference_snapshot,
        )

    @staticmethod
    def _display(value: Any) -> str:
        if isinstance(value, dict):
            return ", ".join(f"{key}={value[key]}" for key in sorted(value))
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)


@dataclass(frozen=True, slots=True)
class LocalVisualCandidateContext:
    portfolio_content_id: UUID
    content_version: int
    production_workflow_id: UUID | None
    production_workflow_version_id: UUID | None
    script_version_id: UUID
    visual_project_id: UUID
    visual_shot_id: UUID
    visual_shot_version_id: UUID
    scene_plan_entry_id: UUID
    candidate_ordinal: int
    seed: int
    provider: str
    model_id: str
    width: int
    height: int
    prompt: str
    negative_prompt: str
    prompt_components: dict[str, Any]
    reference_snapshot: list[dict[str, Any]]


class LocalKeyframeJobAdapter:
    allowed_providers = frozenset({"comfyui-local", "comfyui-sdxl-local"})

    def build_enqueue(
        self,
        context: LocalVisualCandidateContext,
        *,
        actor: str,
        preferred_worker_id: str | None = None,
        timeout_seconds: int = 900,
        max_attempts: int = 3,
    ) -> GenerationJobEnqueue:
        provider = context.provider.strip().lower()
        if provider not in self.allowed_providers:
            raise ValueError("P91 keyframes require a local ComfyUI provider")
        payload = {
            "script_version_id": str(context.script_version_id),
            "visual_project_id": str(context.visual_project_id),
            "visual_shot_id": str(context.visual_shot_id),
            "visual_shot_version_id": str(context.visual_shot_version_id),
            "scene_plan_entry_id": str(context.scene_plan_entry_id),
            "candidate_ordinal": context.candidate_ordinal,
            "seed": context.seed,
            "prompt": context.prompt,
            "negative_prompt": context.negative_prompt,
            "prompt_components": context.prompt_components,
            "continuity_references": context.reference_snapshot,
            "width": context.width,
            "height": context.height,
            "output_contract": {
                "format": "png",
                "register_canonical_asset": True,
                "preserve_seed": True,
                "retain_workflow_metadata": True,
                "checks_required": [
                    "format",
                    "corruption",
                    "unwanted_text",
                    "duplicate",
                    "prompt_coverage",
                    "subject_consistency",
                    "landmark_consistency",
                    "lighting_consistency",
                    "palette_consistency",
                    "framing",
                ],
            },
            "billing": {
                "external_fee_allowed": False,
                "estimated_cost_usd": 0,
                "reserved_cost_usd": 0,
            },
            "requested_by": actor,
        }
        return GenerationJobEnqueue(
            portfolio_content_id=context.portfolio_content_id,
            content_version=context.content_version,
            production_workflow_id=context.production_workflow_id,
            production_workflow_version_id=context.production_workflow_version_id,
            job_type=GenerationJobType.KEYFRAME,
            provider=provider,
            model_id=context.model_id,
            preferred_worker_id=preferred_worker_id,
            idempotency_key=(
                f"p91:keyframe:{context.visual_project_id}:"
                f"{context.visual_shot_version_id}:candidate-{context.candidate_ordinal}:seed-{context.seed}"
            ),
            input_payload=payload,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
            legacy_source={"phase": "P91", "runtime": "local_comfyui"},
        )


def candidate_seed(base_seed: int, *, shot_sequence: int, ordinal: int) -> int:
    return base_seed + (shot_sequence * 1000) + ordinal
