from __future__ import annotations

import json
import random
import re
from typing import Any, Protocol
from urllib import error, request

from src.application.scripts.models import (
    ClaimDraft,
    ClaimSensitivity,
    ClaimSupportStatus,
    ClaimType,
    ScenePlanDraft,
    ScriptDraft,
    ScriptGenerateRequest,
    ScriptSectionDraft,
)


class ScriptAdapterError(RuntimeError):
    pass


class ScriptGenerationAdapter(Protocol):
    name: str

    def generate(
        self,
        *,
        context: dict[str, Any],
        configuration: ScriptGenerateRequest,
    ) -> ScriptDraft: ...


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def estimated_duration_seconds(text: str, words_per_minute: float) -> float:
    return round((word_count(text) / words_per_minute) * 60, 3)


def _fit_words(base_sentences: list[str], target_words: int) -> str:
    if target_words <= 0:
        return ""
    words: list[str] = []
    index = 0
    while len(words) < target_words:
        sentence_words = base_sentences[index % len(base_sentences)].split()
        remaining = target_words - len(words)
        words.extend(sentence_words[:remaining])
        index += 1
    text = " ".join(words).strip()
    if text and text[-1] not in ".?!":
        text += "."
    return text


class DeterministicScriptAdapter:
    name = "deterministic"

    def generate(
        self,
        *,
        context: dict[str, Any],
        configuration: ScriptGenerateRequest,
    ) -> ScriptDraft:
        rng = random.Random(configuration.seed)
        title = str(context.get("title") or "This topic")
        concept = str(context.get("concept") or title)
        tone = str(context.get("tone") or "clear and factual")
        brand_name = str(context.get("brand_name") or "the brand")
        target_words = max(18, round(configuration.target_duration_seconds * configuration.words_per_minute / 60))
        hook_words = max(6, round(target_words * 0.18))
        cta_words = max(5, round(target_words * 0.12))
        narration_words = max(7, target_words - hook_words - cta_words)
        angle = rng.choice((
            "the hidden mechanism",
            "the evidence behind the common assumption",
            "the detail most people overlook",
            "the practical consequence of the central fact",
        ))
        hook = _fit_words(
            [
                f"Most people miss {angle} in {title}",
                f"One verified detail changes how we understand {title}",
            ],
            hook_words,
        )
        narration = _fit_words(
            [
                f"The central question is {concept}",
                f"Start with the observable outcome, then explain the underlying sequence in a {tone} voice",
                "Separate confirmed evidence from interpretation and identify where more research is required",
                "Use one concrete comparison so the audience can follow the mechanism without exaggeration",
            ],
            narration_words,
        )
        cta = _fit_words(
            [
                f"Follow {brand_name} for more evidence-led explanations",
                "Save this for the next time the topic comes up",
            ],
            cta_words,
        )
        section_specs = [
            ("hook", "hook", hook, configuration.target_duration_seconds * 0.18),
            ("body", "narration", narration, configuration.target_duration_seconds * 0.70),
            ("cta", "cta", cta, configuration.target_duration_seconds * 0.12),
        ]
        sections = [
            ScriptSectionDraft(
                section_key=key,
                section_type=section_type,
                text=text,
                target_duration_seconds=round(target, 3),
            )
            for key, section_type, text, target in section_specs
        ]
        scenes = [
            ScenePlanDraft(
                scene_key=f"scene-{index}",
                section_key=section.section_key,
                narration_text=section.text,
                visual_brief=(
                    f"Create an original {configuration.format.replace('_', ' ')} visual sequence for "
                    f"the {section.section_type} section. Use brand-safe graphics, clear hierarchy, and "
                    "rights-cleared or original visual material only."
                ),
                on_screen_text=section.text.split(".")[0][:160],
                target_duration_seconds=section.target_duration_seconds,
                source_requirements=(
                    ["Use only visuals whose rights are approved for production"]
                    if section.section_type != "cta" else []
                ),
            )
            for index, section in enumerate(sections, start=1)
        ]
        claims = [
            ClaimDraft(
                claim_key="claim-hook",
                section_key="hook",
                claim_text=f"The opening framing about {title} is factually supportable.",
                claim_type=ClaimType.FACTUAL,
                confidence=0.55,
                sensitivity=ClaimSensitivity.MEDIUM,
                support_status=ClaimSupportStatus.NEEDS_SOURCE,
                wording_limitations="Do not present the opening as settled fact until a source is linked.",
            ),
            ClaimDraft(
                claim_key="claim-body",
                section_key="body",
                claim_text=f"The central explanation derived from the concept is supported by evidence: {concept[:400]}",
                claim_type=ClaimType.FACTUAL,
                confidence=0.5,
                sensitivity=ClaimSensitivity.MEDIUM,
                support_status=ClaimSupportStatus.NEEDS_SOURCE,
                wording_limitations="Distinguish direct evidence from interpretation and avoid absolute wording.",
            ),
        ]
        return ScriptDraft(
            platform=configuration.platform,
            format=configuration.format,
            language=configuration.language,
            target_duration_seconds=configuration.target_duration_seconds,
            words_per_minute=configuration.words_per_minute,
            duration_tolerance_percent=configuration.duration_tolerance_percent,
            hook_text=hook,
            cta_text=cta,
            sections=sections,
            scenes=scenes,
            claims=claims,
            sources=[],
            claim_sources=[],
            generation_evidence={
                "adapter": self.name,
                "seed": configuration.seed,
                "target_words": target_words,
                "tone": tone,
                "brand_profile_id": str(context.get("brand_profile_id") or ""),
                "claims_default_to_needs_source": True,
            },
        )


class LocalHttpScriptAdapter:
    name = "local_model"

    def __init__(self, *, endpoint: str, model_id: str, timeout_seconds: int = 20) -> None:
        normalized = endpoint.strip().rstrip("/")
        if not normalized.lower().startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
            raise ScriptAdapterError("local script model endpoint must resolve to localhost")
        if not model_id.strip():
            raise ScriptAdapterError("local script model ID is required")
        self.endpoint = normalized
        self.model_id = model_id.strip()
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        context: dict[str, Any],
        configuration: ScriptGenerateRequest,
    ) -> ScriptDraft:
        payload = {
            "model": self.model_id,
            "stream": False,
            "format": "json",
            "options": {"seed": configuration.seed, "temperature": 0},
            "prompt": _local_prompt(context=context, configuration=configuration),
        }
        http_request = request.Request(
            f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ScriptAdapterError(f"local script model request failed: {type(exc).__name__}") from exc
        content = raw.get("response", raw)
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ScriptAdapterError("local script model did not return JSON") from exc
        if not isinstance(content, dict):
            raise ScriptAdapterError("local script model returned an invalid payload")
        content.update({
            "platform": configuration.platform,
            "format": configuration.format,
            "language": configuration.language,
            "target_duration_seconds": configuration.target_duration_seconds,
            "words_per_minute": configuration.words_per_minute,
            "duration_tolerance_percent": configuration.duration_tolerance_percent,
        })
        evidence = dict(content.get("generation_evidence") or {})
        evidence.update({"adapter": self.name, "model_id": self.model_id, "seed": configuration.seed})
        content["generation_evidence"] = evidence
        try:
            return ScriptDraft.model_validate(content)
        except Exception as exc:
            raise ScriptAdapterError(f"local script model output failed validation: {type(exc).__name__}") from exc


def generate_with_fallback(
    *,
    primary: ScriptGenerationAdapter,
    fallback: ScriptGenerationAdapter,
    context: dict[str, Any],
    configuration: ScriptGenerateRequest,
) -> tuple[ScriptDraft, dict[str, Any]]:
    try:
        draft = primary.generate(context=context, configuration=configuration)
        return draft, {"adapter": primary.name, "fallback_used": False}
    except ScriptAdapterError as exc:
        draft = fallback.generate(context=context, configuration=configuration)
        return draft, {
            "adapter": fallback.name,
            "fallback_used": True,
            "fallback_reason": str(exc),
            "requested_adapter": primary.name,
        }


def _local_prompt(*, context: dict[str, Any], configuration: ScriptGenerateRequest) -> str:
    safe_context = {
        "title": context.get("title"),
        "concept": context.get("concept"),
        "tone": context.get("tone"),
        "audience": context.get("audience"),
        "content_restrictions": context.get("content_restrictions"),
        "platform": configuration.platform,
        "format": configuration.format,
        "language": configuration.language,
        "target_duration_seconds": configuration.target_duration_seconds,
        "words_per_minute": configuration.words_per_minute,
        "seed": configuration.seed,
    }
    return (
        "Return JSON only for a versioned script draft with sections, scenes, claims, sources, and "
        "claim_sources matching the application schema. Every narration section must have a scene. "
        "Factual claims without supplied evidence must use support_status needs_source. Never invent "
        "sources, URLs, quotations, or evidence digests. Keep source arrays empty when evidence is absent. "
        f"Context: {json.dumps(safe_context, sort_keys=True, default=str)}"
    )
