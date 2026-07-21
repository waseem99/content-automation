from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib import error, request

from src.application.concepts.models import CandidateDraft, ProductionRoute, RiskLevel
from src.infrastructure.http.local_endpoint import LocalEndpointError, validate_local_http_endpoint


class ConceptAdapterError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConceptSlot:
    ordinal: int
    format: str
    pillar: str


class ConceptGenerationAdapter(Protocol):
    name: str

    def generate(
        self,
        *,
        context: dict[str, Any],
        slots: list[ConceptSlot],
        seed: int,
    ) -> list[CandidateDraft]: ...


def build_slots(
    *,
    format_mix: dict[str, int],
    pillar_targets: dict[str, int],
    seed: int,
) -> list[ConceptSlot]:
    formats = [name for name, count in sorted(format_mix.items()) for _ in range(count)]
    pillars = [name for name, count in sorted(pillar_targets.items()) for _ in range(count)]
    if len(formats) != len(pillars):
        raise ConceptAdapterError("format and pillar totals must match")
    rng = random.Random(seed)
    rng.shuffle(formats)
    rng.shuffle(pillars)
    return [
        ConceptSlot(ordinal=index, format=format_name, pillar=pillar)
        for index, (format_name, pillar) in enumerate(zip(formats, pillars, strict=True), start=1)
    ]


class DeterministicConceptAdapter:
    name = "deterministic"

    HOOK_PATTERNS = (
        "Most people miss this about {pillar}: {specificity}.",
        "Before you believe the obvious answer, look at {specificity}.",
        "The surprising part of {pillar} is not what happens—it is why {specificity}.",
        "One small detail changes how you understand {pillar}: {specificity}.",
        "What looks ordinary in {pillar} becomes remarkable when {specificity}.",
    )
    ANGLES = (
        "myth-versus-evidence",
        "step-by-step-explainer",
        "hidden-mechanism",
        "comparison",
        "practical-checklist",
        "before-and-after",
        "frequently-misunderstood-question",
        "evidence-led-story",
    )

    def generate(
        self,
        *,
        context: dict[str, Any],
        slots: list[ConceptSlot],
        seed: int,
    ) -> list[CandidateDraft]:
        rng = random.Random(seed)
        brand_name = str(context.get("brand_name") or "the brand")
        niche = str(context.get("niche") or "the topic")
        audience = context.get("audience") or {}
        audience_label = _audience_label(audience)
        reference_patterns = list(context.get("reference_patterns") or [])
        performance_signals = list(context.get("performance_signals") or [])
        restrictions = context.get("content_restrictions") or {}
        candidates: list[CandidateDraft] = []
        for slot in slots:
            angle = self.ANGLES[(slot.ordinal + seed) % len(self.ANGLES)]
            pattern = self.HOOK_PATTERNS[(slot.ordinal * 3 + seed) % len(self.HOOK_PATTERNS)]
            reference = reference_patterns[(slot.ordinal - 1) % len(reference_patterns)] if reference_patterns else None
            performance = performance_signals[(slot.ordinal - 1) % len(performance_signals)] if performance_signals else None
            specificity = _specificity(slot.pillar, niche, slot.ordinal, rng)
            title = _title(slot.pillar, angle, slot.ordinal)
            hook = pattern.format(pillar=slot.pillar.replace("_", " "), specificity=specificity)
            concept = (
                f"Create a {slot.format.replace('_', ' ')} for {audience_label} that explores "
                f"{slot.pillar.replace('_', ' ')} through a {angle.replace('-', ' ')} angle. "
                f"Open with the hook, establish one concrete question, show two to four evidence-led "
                f"beats, and close with a brand-appropriate takeaway for {brand_name}. "
                f"The piece must remain original and must not reproduce source wording or source media."
            )
            rationale_parts = [
                f"Fills the {slot.pillar.replace('_', ' ')} pillar",
                f"uses the requested {slot.format.replace('_', ' ')} format",
                f"and gives the audience a specific {angle.replace('-', ' ')} reason to continue watching.",
            ]
            if performance:
                rationale_parts.append("The pacing recommendation is informed by an internal historical performance signal.")
            if reference:
                rationale_parts.append("The structure is informed by an approved abstract reference pattern, not copied content.")
            required_research = [
                f"Verify the central factual claim behind {specificity}",
                f"Find at least two independent sources for {slot.pillar.replace('_', ' ')}",
            ]
            source_requirements = [
                "Primary or authoritative source for the central mechanism",
                "Secondary corroborating source with publication date",
            ]
            factual_risk = _risk_for_angle(angle)
            complexity = _complexity_for_format(slot.format)
            estimated_cost, route = _cost_and_route(slot.format, complexity)
            candidates.append(
                CandidateDraft(
                    title=title,
                    hook=hook,
                    concept=concept,
                    format=slot.format,
                    pillar=slot.pillar,
                    rationale=" ".join(rationale_parts),
                    source_requirements=source_requirements,
                    required_research=required_research,
                    factual_risk=factual_risk,
                    production_complexity=complexity,
                    estimated_cost_usd=estimated_cost,
                    recommended_route=route,
                    generation_evidence={
                        "adapter": self.name,
                        "seed": seed,
                        "slot": slot.ordinal,
                        "angle": angle,
                        "reference_source_id": reference.get("reference_source_id") if reference else None,
                        "reference_pattern": reference.get("pattern") if reference else None,
                        "performance_package_id": performance.get("platform_package_id") if performance else None,
                        "performance_signal": performance.get("signal") if performance else None,
                        "restrictions_considered": restrictions,
                    },
                )
            )
        return candidates


class LocalHttpConceptAdapter:
    name = "local_model"

    def __init__(self, *, endpoint: str, model_id: str, timeout_seconds: int = 20) -> None:
        try:
            self.endpoint = validate_local_http_endpoint(endpoint)
        except LocalEndpointError as exc:
            raise ConceptAdapterError(str(exc)) from exc
        if not model_id.strip():
            raise ConceptAdapterError("local model ID is required")
        self.model_id = model_id.strip()
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        context: dict[str, Any],
        slots: list[ConceptSlot],
        seed: int,
    ) -> list[CandidateDraft]:
        payload = {
            "model": self.model_id,
            "stream": False,
            "format": "json",
            "options": {"seed": seed, "temperature": 0},
            "prompt": _local_prompt(context=context, slots=slots, seed=seed),
        }
        http_request = request.Request(
            f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # nosec B310 -- endpoint is parsed and restricted to loopback HTTP in __init__.
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ConceptAdapterError(f"local model request failed: {type(exc).__name__}") from exc
        content = raw.get("response", raw)
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ConceptAdapterError("local model did not return JSON") from exc
        rows = content.get("candidates") if isinstance(content, dict) else content
        if not isinstance(rows, list) or len(rows) != len(slots):
            raise ConceptAdapterError("local model returned the wrong candidate count")
        candidates = []
        for slot, row in zip(slots, rows, strict=True):
            if not isinstance(row, dict):
                raise ConceptAdapterError("local model candidate must be an object")
            row["format"] = slot.format
            row["pillar"] = slot.pillar
            evidence = dict(row.get("generation_evidence") or {})
            evidence.update({"adapter": self.name, "model_id": self.model_id, "seed": seed, "slot": slot.ordinal})
            row["generation_evidence"] = evidence
            candidates.append(CandidateDraft.model_validate(row))
        return candidates


def generate_with_fallback(
    *,
    primary: ConceptGenerationAdapter,
    fallback: ConceptGenerationAdapter,
    context: dict[str, Any],
    slots: list[ConceptSlot],
    seed: int,
) -> tuple[list[CandidateDraft], dict[str, Any]]:
    try:
        candidates = primary.generate(context=context, slots=slots, seed=seed)
        return candidates, {"adapter": primary.name, "fallback_used": False}
    except ConceptAdapterError as exc:
        candidates = fallback.generate(context=context, slots=slots, seed=seed)
        return candidates, {
            "adapter": fallback.name,
            "fallback_used": True,
            "fallback_reason": str(exc),
            "requested_adapter": primary.name,
        }


def _local_prompt(*, context: dict[str, Any], slots: list[ConceptSlot], seed: int) -> str:
    schema = {
        "candidates": [
            {
                "title": "3-240 chars",
                "hook": "3-500 chars",
                "concept": "20-5000 chars",
                "rationale": "20-5000 chars",
                "source_requirements": ["source requirement"],
                "required_research": ["research task"],
                "factual_risk": "low|medium|high",
                "production_complexity": "low|medium|high",
                "estimated_cost_usd": 0,
                "recommended_route": "local|hybrid|managed",
            }
        ]
    }
    safe_context = {
        "brand_name": context.get("brand_name"),
        "niche": context.get("niche"),
        "audience": context.get("audience"),
        "tone": context.get("tone"),
        "content_restrictions": context.get("content_restrictions"),
        "visual_rules": context.get("visual_rules"),
        "reference_patterns": context.get("reference_patterns"),
        "performance_signals": context.get("performance_signals"),
    }
    return (
        "Return JSON only. Generate one original content concept for every supplied slot. "
        "Do not copy source wording or media. Keep the exact slot order and do not change format or pillar. "
        f"Seed: {seed}. Context: {json.dumps(safe_context, sort_keys=True, default=str)}. "
        f"Slots: {json.dumps([asdict(slot) for slot in slots], default=str)}. "
        f"Required response schema: {json.dumps(schema)}"
    )


def _audience_label(audience: Any) -> str:
    if isinstance(audience, dict):
        values = [str(value) for value in audience.values() if value]
        if values:
            return ", ".join(values[:3])
    return "the brand's target audience"


def _specificity(pillar: str, niche: str, ordinal: int, rng: random.Random) -> str:
    details = (
        "a common assumption breaks down under evidence",
        "a hidden sequence explains the visible outcome",
        "two similar cases produce very different results",
        "one measurable signal reveals what is really happening",
        "a practical decision changes when context is added",
    )
    return f"{details[(ordinal + rng.randrange(len(details))) % len(details)]} in {niche.lower()}"


def _title(pillar: str, angle: str, ordinal: int) -> str:
    readable = pillar.replace("_", " ").title()
    angle_label = angle.replace("-", " ").title()
    return f"{readable}: {angle_label} #{ordinal:02d}"


def _risk_for_angle(angle: str) -> RiskLevel:
    if angle in {"myth-versus-evidence", "evidence-led-story"}:
        return RiskLevel.HIGH
    if angle in {"comparison", "hidden-mechanism", "frequently-misunderstood-question"}:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _complexity_for_format(format_name: str) -> RiskLevel:
    normalized = format_name.lower()
    if any(token in normalized for token in ("feature", "long", "cinematic", "premium")):
        return RiskLevel.HIGH
    if any(token in normalized for token in ("carousel", "explainer", "mixed")):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _cost_and_route(format_name: str, complexity: RiskLevel) -> tuple[float, ProductionRoute]:
    if complexity == RiskLevel.HIGH:
        return 18.0, ProductionRoute.HYBRID
    if complexity == RiskLevel.MEDIUM:
        return 4.0, ProductionRoute.LOCAL
    return 0.0, ProductionRoute.LOCAL
