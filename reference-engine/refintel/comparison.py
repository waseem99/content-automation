from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, select_autoescape
from pydantic import BaseModel, Field

from .fingerprint import load_fingerprint, text_similarity
from .models import ReferenceFingerprint, RightsDeclaration


class ComparisonStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    REUSED = "reused"


class GateDecision(StrEnum):
    REVIEW = "review"
    BLOCK = "block"


class ReferenceFailure(BaseModel):
    input_label: str
    reason: str
    fallback_action: str = "Use an authorized local export and process it with ingest-file."


class RightsGateRecord(BaseModel):
    reference_id: str
    declaration: str | None = None
    comparison_allowed: bool = False
    source_asset_use_allowed: bool = False
    production_use_allowed: bool = False
    decision: GateDecision = GateDecision.BLOCK
    reasons: list[str] = Field(default_factory=list)
    human_review_required: bool = True


class ReferenceProfile(BaseModel):
    reference_id: str
    title: str
    platform: str
    brand_id: str
    format_name: str
    rights_declaration: str | None = None
    fingerprint_sha256: str
    hook_type: str
    story_stages: list[str]
    pacing: dict[str, float]
    visual_terms: list[str]
    audio_terms: list[str]
    mechanics_terms: list[str]
    source_specific_elements_to_exclude: list[str]
    transcript_available: bool = False
    limitations: list[str] = Field(default_factory=list)


class PairwiseComparison(BaseModel):
    left_reference_id: str
    right_reference_id: str
    overall_similarity: float = Field(ge=0, le=1)
    hook_similarity: float = Field(ge=0, le=1)
    story_similarity: float = Field(ge=0, le=1)
    pacing_similarity: float = Field(ge=0, le=1)
    visual_similarity: float = Field(ge=0, le=1)
    audio_similarity: float = Field(ge=0, le=1)
    mechanics_similarity: float = Field(ge=0, le=1)
    brand_similarity: float = Field(ge=0, le=1)
    format_similarity: float = Field(ge=0, le=1)
    platform_similarity: float = Field(ge=0, le=1)
    shared_abstract_terms: list[str] = Field(default_factory=list)
    source_specific_expression_compared: bool = False


class PatternRecord(BaseModel):
    pattern_id: str
    category: str
    value: str
    description: str
    support_reference_ids: list[str]
    support_count: int
    platforms: list[str]
    brands: list[str]
    formats: list[str]
    eligible_for_original_brief: bool
    evidence_type: str = "derived_from_abstract_reference_features"
    source_specific_expression_included: bool = False
    human_review_required: bool = True


class ReferenceCluster(BaseModel):
    cluster_id: str
    member_reference_ids: list[str]
    brands: list[str]
    formats: list[str]
    platforms: list[str]
    dominant_hook_type: str | None = None
    recurring_story_stages: list[str] = Field(default_factory=list)
    recurring_abstract_terms: list[str] = Field(default_factory=list)
    mean_internal_similarity: float
    singleton: bool
    human_review_required: bool = True


class OriginalityCheck(BaseModel):
    reference_id: str
    transcript_available: bool
    text_similarity_score: float = Field(ge=0, le=1)
    longest_shared_phrase_words: int = Field(ge=0)
    source_title_reused: bool
    blocked: bool
    source_excerpt_persisted: bool = False


class OriginalityGate(BaseModel):
    schema_version: str = "p75.originality_gate.v1"
    decision: GateDecision
    checks: list[OriginalityCheck]
    block_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    required_transformations: list[str]
    source_media_use_allowed: bool = False
    automatic_approval: bool = False
    human_review_required: bool = True


class PatternBrief(BaseModel):
    schema_version: str = "p75.pattern_brief.v1"
    status: str = "draft_for_human_review"
    brand_id: str
    target_format: str
    topic: str
    source_reference_ids: list[str]
    abstract_patterns: list[str]
    creative_direction: list[str]
    originality_constraints: list[str]
    source_traceability: dict[str, Any]
    source_assets_allowed: bool = False
    automatic_generation_allowed: bool = False
    automatic_publication_allowed: bool = False
    human_review_required: bool = True


class ComparisonReport(BaseModel):
    schema_version: str = "p75.reference_comparison.v1"
    status: ComparisonStatus
    input_digest: str
    reference_count: int
    profiles: list[ReferenceProfile]
    failures: list[ReferenceFailure]
    rights_gates: list[RightsGateRecord]
    pairwise: list[PairwiseComparison]
    clusters: list[ReferenceCluster]
    patterns: list[PatternRecord]
    pattern_brief: PatternBrief | None = None
    originality_gate: OriginalityGate | None = None
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    ready_for_human_review: bool = False
    source_media_must_not_enter_generated_content: bool = True
    source_text_must_not_be_reused_verbatim: bool = True
    source_identities_watermarks_voices_music_excluded: bool = True
    automatic_generation: bool = False
    automatic_publication: bool = False
    human_review_required: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


CONTROLLED_TERMS: dict[str, tuple[str, ...]] = {
    "close_up": ("close up", "close-up", "tight framing"),
    "wide_shot": ("wide shot", "wide framing", "establishing shot"),
    "camera_motion": ("camera motion", "pan", "tilt", "tracking", "zoom"),
    "fast_cuts": ("fast cut", "rapid cut", "quick cut"),
    "slow_pacing": ("slow pacing", "slow pace", "long take"),
    "on_screen_captions": ("caption", "on-screen text", "on screen text", "subtitle"),
    "highlighted_words": ("highlighted word", "word emphasis", "text emphasis"),
    "curiosity_hook": ("curiosity", "question hook", "open loop"),
    "immediate_hook": ("immediate hook", "first second", "opening second"),
    "escalation": ("escalat", "rising tension", "increasing stakes"),
    "reveal": ("reveal", "surprise", "twist"),
    "payoff": ("payoff", "resolution", "answer"),
    "post_payoff_cta": ("cta after", "call to action after", "after the payoff"),
    "narration": ("narration", "voiceover", "voice-over"),
    "music_energy": ("music energy", "music build", "sound build"),
    "sound_emphasis": ("sound effect", "audio emphasis", "impact sound"),
    "silent_readable": ("without audio", "sound off", "silent viewing"),
}

ORIGINALITY_CONSTRAINTS = [
    "Create a new concept and factual angle rather than retelling a source-specific story.",
    "Write entirely new narration and captions; do not paraphrase line by line.",
    "Use newly created or separately licensed footage, imagery, graphics, and animation.",
    "Use a distinct setting, composition, shot order, visual identity, and color treatment.",
    "Do not use source identities, likenesses, characters, logos, watermarks, or branding.",
    "Do not imitate a source voice or reuse source music, recordings, or sound design.",
    "Complete human originality and rights review before generation or rendering.",
]

HOOK_LABELS = {
    "curiosity",
    "delayed_context",
    "immediate_visual",
    "spoken_question",
    "text_hook",
    "visual_hook",
}


def _hook_label(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    if normalized in HOOK_LABELS:
        return normalized
    if "immediate" in normalized:
        return "immediate_visual"
    if "delay" in normalized:
        return "delayed_context"
    if "question" in normalized:
        return "spoken_question"
    if "curiosity" in normalized or "open_loop" in normalized:
        return "curiosity"
    return "unconfirmed"


def _story_stage(value: object, index: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    mappings = (
        (("hook", "open"), "opening"),
        (("setup", "context"), "setup"),
        (("develop", "escalat", "rise", "middle"), "development"),
        (("payoff", "reveal", "resol", "answer"), "payoff"),
        (("cta", "close", "call_to_action"), "cta_or_close"),
    )
    for candidates, label in mappings:
        if any(candidate in normalized for candidate in candidates):
            return label
    return f"structural_beat_{index + 1}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_error(exc: Exception) -> str:
    message = re.sub(r"(?:[A-Za-z]:)?[/\\][^\s]+", "<local-path>", str(exc))
    return message[:300] or type(exc).__name__


def _canonical_terms(*values: object) -> list[str]:
    text = " ".join(str(value).lower().replace("_", " ") for value in values)
    return sorted(
        term
        for term, aliases in CONTROLLED_TERMS.items()
        if any(alias in text for alias in aliases)
    )


def _numeric(value: object) -> float:
    try:
        return round(float(value or 0), 4)
    except (TypeError, ValueError):
        return 0.0


def _infer_format(fingerprint: ReferenceFingerprint, project_payload: dict[str, Any]) -> str:
    media = project_payload.get("media") or {}
    orientation = str(media.get("orientation") or "unknown")
    duration = fingerprint.duration_seconds
    length = "short" if duration <= 90 else "long"
    return f"{orientation}_{length}"


def _project_payload(fingerprint_path: Path) -> tuple[dict[str, Any], Path | None]:
    project_path = fingerprint_path.parent.parent / "project.json"
    if not project_path.is_file():
        return {}, None
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("project.json must contain an object")
    transcript_path = fingerprint_path.parent.parent / "transcript" / "transcript.txt"
    return payload, transcript_path if transcript_path.is_file() else None


def _profile(
    fingerprint_path: Path,
    metadata: dict[str, dict[str, str]],
) -> tuple[ReferenceProfile, RightsGateRecord, Path | None]:
    fingerprint = load_fingerprint(fingerprint_path)
    project, transcript_path = _project_payload(fingerprint_path)
    access = project.get("access") or {}
    declaration = access.get("declaration")
    valid_rights = declaration in {item.value for item in RightsDeclaration}
    rights = RightsGateRecord(
        reference_id=fingerprint.reference_id,
        declaration=str(declaration) if declaration else None,
        comparison_allowed=valid_rights,
        decision=GateDecision.REVIEW if valid_rights else GateDecision.BLOCK,
        reasons=(
            [
                "Rights declaration permits internal comparison only; "
                "source assets remain excluded.",
                "Production use requires separate asset-level clearance and human approval.",
            ]
            if valid_rights
            else ["A valid rights declaration is required before comparison."]
        ),
    )
    item_metadata = metadata.get(fingerprint.reference_id, {})
    sequence = fingerprint.visual_language.get("sequence_storytelling") or {}
    reusable = sequence.get("reusable_mechanics") if isinstance(sequence, dict) else []
    story_stages = [
        _story_stage(stage.get("stage"), index)
        for index, stage in enumerate(fingerprint.story_arc)
        if isinstance(stage, dict)
    ]
    limitations: list[str] = []
    if not project:
        limitations.append("project.json unavailable; rights and format evidence are incomplete.")
    if not transcript_path:
        limitations.append("Transcript unavailable for source-text overlap checking.")
    return (
        ReferenceProfile(
            reference_id=fingerprint.reference_id,
            title=fingerprint.title,
            platform=fingerprint.platform.value,
            brand_id=item_metadata.get("brand_id", "unassigned"),
            format_name=item_metadata.get("format_name", _infer_format(fingerprint, project)),
            rights_declaration=str(declaration) if declaration else None,
            fingerprint_sha256=_sha256(fingerprint_path),
            hook_type=_hook_label(fingerprint.hook.get("hook_type")),
            story_stages=story_stages,
            pacing={
                "visual_changes_per_minute": _numeric(
                    fingerprint.pacing.get("visual_changes_per_minute")
                ),
                "caption_changes_per_minute": _numeric(
                    fingerprint.pacing.get("caption_changes_per_minute")
                ),
                "average_shot_seconds": _numeric(fingerprint.pacing.get("average_shot_seconds")),
            },
            visual_terms=_canonical_terms(fingerprint.visual_language),
            audio_terms=_canonical_terms(fingerprint.audio_language),
            mechanics_terms=_canonical_terms(fingerprint.reusable_mechanics, reusable),
            source_specific_elements_to_exclude=list(
                dict.fromkeys(
                    [
                        *fingerprint.source_specific_elements_to_exclude,
                        "source identities and likenesses",
                        "source watermarks and branding",
                        "source voices, music, and sound recordings",
                    ]
                )
            ),
            transcript_available=bool(transcript_path),
            limitations=limitations,
        ),
        rights,
        transcript_path,
    )


def _set_similarity(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _pacing_similarity(left: ReferenceProfile, right: ReferenceProfile) -> float:
    scores: list[float] = []
    for key in sorted(left.pacing):
        first, second = left.pacing[key], right.pacing[key]
        scores.append(1 - min(1.0, abs(first - second) / max(first, second, 1.0)))
    return sum(scores) / len(scores)


def _pair(left: ReferenceProfile, right: ReferenceProfile) -> PairwiseComparison:
    hook = 1.0 if left.hook_type == right.hook_type else 0.0
    story = _set_similarity(left.story_stages, right.story_stages)
    pacing = _pacing_similarity(left, right)
    visual = _set_similarity(left.visual_terms, right.visual_terms)
    audio = _set_similarity(left.audio_terms, right.audio_terms)
    mechanics = _set_similarity(left.mechanics_terms, right.mechanics_terms)
    brand = 1.0 if left.brand_id != "unassigned" and left.brand_id == right.brand_id else 0.0
    format_score = 1.0 if left.format_name == right.format_name else 0.0
    platform = 1.0 if left.platform == right.platform else 0.0
    overall = (
        hook * 0.12
        + story * 0.18
        + pacing * 0.17
        + visual * 0.13
        + audio * 0.08
        + mechanics * 0.17
        + brand * 0.05
        + format_score * 0.05
        + platform * 0.05
    )
    shared = sorted(
        (set(left.visual_terms) | set(left.audio_terms) | set(left.mechanics_terms))
        & (set(right.visual_terms) | set(right.audio_terms) | set(right.mechanics_terms))
    )
    return PairwiseComparison(
        left_reference_id=left.reference_id,
        right_reference_id=right.reference_id,
        overall_similarity=round(overall, 4),
        hook_similarity=round(hook, 4),
        story_similarity=round(story, 4),
        pacing_similarity=round(pacing, 4),
        visual_similarity=round(visual, 4),
        audio_similarity=round(audio, 4),
        mechanics_similarity=round(mechanics, 4),
        brand_similarity=brand,
        format_similarity=format_score,
        platform_similarity=platform,
        shared_abstract_terms=shared,
    )


def _recurring(values: list[list[str]], minimum: int = 2) -> list[str]:
    counts = Counter(value for items in values for value in set(items))
    return sorted(value for value, count in counts.items() if count >= minimum)


def _clusters(
    profiles: list[ReferenceProfile],
    pairwise: list[PairwiseComparison],
    threshold: float,
) -> list[ReferenceCluster]:
    neighbors: dict[str, set[str]] = {profile.reference_id: set() for profile in profiles}
    score_by_pair: dict[frozenset[str], float] = {}
    for pair in pairwise:
        key = frozenset((pair.left_reference_id, pair.right_reference_id))
        score_by_pair[key] = pair.overall_similarity
        if pair.overall_similarity >= threshold:
            neighbors[pair.left_reference_id].add(pair.right_reference_id)
            neighbors[pair.right_reference_id].add(pair.left_reference_id)
    by_id = {profile.reference_id: profile for profile in profiles}
    remaining = set(by_id)
    results: list[ReferenceCluster] = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        members: set[str] = set()
        while stack:
            current = stack.pop()
            if current in members:
                continue
            members.add(current)
            stack.extend(sorted(neighbors[current] - members, reverse=True))
        remaining -= members
        member_ids = sorted(members)
        items = [by_id[item] for item in member_ids]
        internal = [score for key, score in score_by_pair.items() if len(key & members) == 2]
        hooks = Counter(item.hook_type for item in items)
        cluster_hash = hashlib.sha256("|".join(member_ids).encode()).hexdigest()[:10]
        results.append(
            ReferenceCluster(
                cluster_id=f"cluster-{cluster_hash}",
                member_reference_ids=member_ids,
                brands=sorted({item.brand_id for item in items}),
                formats=sorted({item.format_name for item in items}),
                platforms=sorted({item.platform for item in items}),
                dominant_hook_type=hooks.most_common(1)[0][0] if hooks else None,
                recurring_story_stages=_recurring([item.story_stages for item in items]),
                recurring_abstract_terms=_recurring(
                    [item.visual_terms + item.audio_terms + item.mechanics_terms for item in items]
                ),
                mean_internal_similarity=(
                    round(sum(internal) / len(internal), 4) if internal else 1.0
                ),
                singleton=len(items) == 1,
            )
        )
    return sorted(results, key=lambda item: item.cluster_id)


def _pattern_description(category: str, value: str) -> str:
    readable = value.replace("_", " ")
    templates = {
        "hook": f"Recurring hook family: {readable}.",
        "story_stage": f"Recurring structural stage: {readable}.",
        "visual": f"Recurring abstract visual mechanic: {readable}.",
        "audio": f"Recurring abstract audio mechanic: {readable}.",
        "mechanic": f"Recurring engagement/editing mechanic: {readable}.",
        "format": f"Recurring delivery format: {readable}.",
    }
    return templates[category]


def _patterns(
    profiles: list[ReferenceProfile], rights: list[RightsGateRecord]
) -> list[PatternRecord]:
    rights_by_id = {item.reference_id: item for item in rights}
    occurrences: dict[tuple[str, str], list[ReferenceProfile]] = defaultdict(list)
    for profile in profiles:
        occurrences[("hook", profile.hook_type)].append(profile)
        occurrences[("format", profile.format_name)].append(profile)
        for value in set(profile.story_stages):
            occurrences[("story_stage", value)].append(profile)
        for category, values in (
            ("visual", profile.visual_terms),
            ("audio", profile.audio_terms),
            ("mechanic", profile.mechanics_terms),
        ):
            for value in set(values):
                occurrences[(category, value)].append(profile)
    results: list[PatternRecord] = []
    for (category, value), items in sorted(occurrences.items()):
        member_ids = sorted({item.reference_id for item in items})
        if len(member_ids) < 2 or value in {"", "unconfirmed"}:
            continue
        pattern_hash = hashlib.sha256(f"{category}:{value}".encode()).hexdigest()[:10]
        eligible = all(rights_by_id[item].comparison_allowed for item in member_ids)
        results.append(
            PatternRecord(
                pattern_id=f"pattern-{pattern_hash}",
                category=category,
                value=value,
                description=_pattern_description(category, value),
                support_reference_ids=member_ids,
                support_count=len(member_ids),
                platforms=sorted({item.platform for item in items}),
                brands=sorted({item.brand_id for item in items}),
                formats=sorted({item.format_name for item in items}),
                eligible_for_original_brief=eligible,
            )
        )
    return results


def _longest_shared_phrase_words(candidate: str, source: str, maximum: int = 20) -> int:
    candidate_tokens = re.findall(r"[a-z0-9]+", candidate.lower())
    source_tokens = re.findall(r"[a-z0-9]+", source.lower())
    if not candidate_tokens or not source_tokens:
        return 0
    source_ngrams: dict[int, set[tuple[str, ...]]] = {}
    upper = min(maximum, len(candidate_tokens), len(source_tokens))
    for size in range(upper, 3, -1):
        if size not in source_ngrams:
            source_ngrams[size] = {
                tuple(source_tokens[index : index + size])
                for index in range(len(source_tokens) - size + 1)
            }
        if any(
            tuple(candidate_tokens[index : index + size]) in source_ngrams[size]
            for index in range(len(candidate_tokens) - size + 1)
        ):
            return size
    return 0


def evaluate_originality_text(
    candidate_text: str,
    profiles: list[ReferenceProfile],
    transcript_paths: dict[str, Path | None],
) -> OriginalityGate:
    checks: list[OriginalityCheck] = []
    block_reasons: list[str] = []
    limitations: list[str] = [
        "Automated visual identity, watermark, likeness, voice, music, and asset-rights "
        "clearance is not asserted; source assets remain excluded."
    ]
    normalized_candidate = " ".join(re.findall(r"[a-z0-9]+", candidate_text.lower()))
    for profile in profiles:
        transcript_path = transcript_paths.get(profile.reference_id)
        transcript = (
            transcript_path.read_text(encoding="utf-8", errors="replace")
            if transcript_path and transcript_path.is_file()
            else ""
        )
        similarity = text_similarity(candidate_text, transcript) if transcript else 0.0
        phrase_words = _longest_shared_phrase_words(candidate_text, transcript) if transcript else 0
        normalized_title = " ".join(re.findall(r"[a-z0-9]+", profile.title.lower()))
        title_reused = (
            len(normalized_title.split()) >= 2 and normalized_title in normalized_candidate
        )
        blocked = similarity >= 0.35 or phrase_words >= 8 or title_reused
        if blocked:
            block_reasons.append(
                f"Candidate overlaps source-specific text or title for {profile.reference_id}."
            )
        if not transcript:
            limitations.append(
                f"Transcript unavailable for {profile.reference_id}; "
                "source-text overlap is unmeasured."
            )
        checks.append(
            OriginalityCheck(
                reference_id=profile.reference_id,
                transcript_available=bool(transcript),
                text_similarity_score=similarity,
                longest_shared_phrase_words=phrase_words,
                source_title_reused=title_reused,
                blocked=blocked,
            )
        )
    return OriginalityGate(
        decision=GateDecision.BLOCK if block_reasons else GateDecision.REVIEW,
        checks=checks,
        block_reasons=block_reasons,
        limitations=limitations,
        required_transformations=ORIGINALITY_CONSTRAINTS,
    )


def _brief(
    profiles: list[ReferenceProfile],
    patterns: list[PatternRecord],
    *,
    brand_id: str,
    target_format: str,
    topic: str | None,
) -> PatternBrief | None:
    eligible = [pattern for pattern in patterns if pattern.eligible_for_original_brief]
    if len(profiles) < 2 or not eligible:
        return None
    selected = eligible[:12]
    return PatternBrief(
        brand_id=brand_id,
        target_format=target_format,
        topic=topic or "New editorial topic to be selected during human review",
        source_reference_ids=sorted(profile.reference_id for profile in profiles),
        abstract_patterns=[pattern.description for pattern in selected],
        creative_direction=[
            "Use recurring mechanics as performance hypotheses, not a source-matching recipe.",
            "Develop a new hook, narrative wording, scene plan, payoff, and brand treatment.",
            "Test at least two original executions and select on retention "
            "and monetization quality.",
        ],
        originality_constraints=ORIGINALITY_CONSTRAINTS,
        source_traceability={
            "pattern_ids": [pattern.pattern_id for pattern in selected],
            "source_specific_expression_included": False,
            "source_text_included": False,
            "source_assets_included": False,
        },
    )


def _facets(profiles: list[ReferenceProfile]) -> dict[str, dict[str, int]]:
    return {
        name: dict(sorted(Counter(getattr(item, field) for item in profiles).items()))
        for name, field in (
            ("brands", "brand_id"),
            ("formats", "format_name"),
            ("platforms", "platform"),
            ("hooks", "hook_type"),
        )
    }


def _digest(
    fingerprint_paths: list[Path],
    metadata: dict[str, dict[str, str]],
    cluster_threshold: float,
    brand_id: str,
    target_format: str,
    topic: str | None,
) -> str:
    payload = {
        "fingerprints": [
            {
                "label": path.name,
                "sha256": _sha256(path),
                "project_sha256": (
                    _sha256(path.parent.parent / "project.json")
                    if (path.parent.parent / "project.json").is_file()
                    else None
                ),
                "transcript_sha256": (
                    _sha256(path.parent.parent / "transcript" / "transcript.txt")
                    if (path.parent.parent / "transcript" / "transcript.txt").is_file()
                    else None
                ),
            }
            for path in sorted(fingerprint_paths, key=lambda item: str(item))
            if path.is_file()
        ],
        "metadata": metadata,
        "cluster_threshold": cluster_threshold,
        "brand_id": brand_id,
        "target_format": target_format,
        "topic": topic,
        "schema": "p75.reference_comparison.v1",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _render_html(report: ComparisonReport, target: Path) -> None:
    template = Environment(
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
    ).from_string(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>P75 Cross-reference intelligence</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#f5f6f8;background:#0b0d12}
*{box-sizing:border-box}body{margin:0}.shell{max-width:1380px;margin:auto;padding:24px}
.card{background:#151821;border:1px solid #2a2f3a;border-radius:14px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}
.kicker{color:#ffcf33;text-transform:uppercase;letter-spacing:.1em;font-size:12px}
.muted{color:#a7adbb}.warning{border-left:4px solid #ffcf33;background:#211e12;padding:12px}
.block{border-left:4px solid #ff6363}.score{font-size:28px;color:#ffcf33}pre{white-space:pre-wrap}
@media(max-width:700px){.shell{padding:12px}}
</style></head><body><main class="shell">
<div class="kicker">P75 cross-reference intelligence</div><h1>Pattern and originality review</h1>
<p class="muted">{{ report.reference_count }} valid references · {{ report.status }}</p>
<div class="warning">Abstract mechanics only. Source footage, wording, identities, watermarks,
voices, music, branding, and compositions remain excluded. Human review is mandatory.</div>
<section class="grid">
{% for cluster in report.clusters %}<article class="card"><h2>{{ cluster.cluster_id }}</h2>
<div class="score">{{ cluster.member_reference_ids|length }}</div><p>references</p>
<p>{{ cluster.platforms|join(', ') }} · {{ cluster.formats|join(', ') }}</p>
<pre>{{ cluster.recurring_abstract_terms|join('\n') }}</pre></article>{% endfor %}
</section><section class="card"><h2>Reusable pattern candidates</h2><div class="grid">
{% for pattern in report.patterns %}<article><strong>{{ pattern.description }}</strong>
<p class="muted">support {{ pattern.support_count }} · {{ pattern.platforms|join(', ') }}</p>
</article>{% endfor %}</div></section>
<section class="grid"><article class="card"><h2>Rights gates</h2><pre>{{ rights }}</pre></article>
<article class="card"><h2>Originality gate</h2><pre>{{ originality }}</pre></article>
<article class="card"><h2>Draft pattern brief</h2><pre>{{ brief }}</pre></article>
<article class="card"><h2>Limitations and failures</h2>
<pre>{{ limitations }}</pre></article></section>
</main></body></html>"""
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        template.render(
            report=report.model_dump(mode="json"),
            rights=json.dumps(
                [item.model_dump(mode="json") for item in report.rights_gates], indent=2
            ),
            originality=(
                report.originality_gate.model_dump_json(indent=2)
                if report.originality_gate
                else "Unavailable"
            ),
            brief=(
                report.pattern_brief.model_dump_json(indent=2)
                if report.pattern_brief
                else "Unavailable"
            ),
            limitations=json.dumps(
                {
                    "limitations": report.limitations,
                    "failures": [item.model_dump(mode="json") for item in report.failures],
                },
                indent=2,
            ),
        ),
        encoding="utf-8",
    )


def load_comparison_metadata(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Comparison metadata must be an object keyed by reference ID")
    result: dict[str, dict[str, str]] = {}
    for reference_id, values in payload.items():
        if not isinstance(values, dict):
            raise ValueError(f"Metadata for {reference_id} must be an object")
        result[str(reference_id)] = {
            key: str(values[key]) for key in ("brand_id", "format_name") if values.get(key)
        }
    return result


def build_comparison_library(
    fingerprint_paths: list[Path],
    output_dir: Path,
    *,
    metadata: dict[str, dict[str, str]] | None = None,
    cluster_threshold: float = 0.62,
    brand_id: str = "unassigned",
    target_format: str = "vertical_short",
    topic: str | None = None,
    force: bool = False,
) -> tuple[ComparisonReport, Path, Path]:
    if not 0 <= cluster_threshold <= 1:
        raise ValueError("cluster_threshold must be between 0 and 1")
    metadata = metadata or {}
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "comparison_report.json"
    html_path = output_dir / "index.html"
    digest = _digest(
        fingerprint_paths,
        metadata,
        cluster_threshold,
        brand_id,
        target_format,
        topic,
    )
    if report_path.is_file() and not force:
        previous = ComparisonReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        if previous.input_digest == digest:
            reused = previous.model_copy(
                update={"status": ComparisonStatus.REUSED, "generated_at": datetime.now(UTC)}
            )
            report_path.write_text(reused.model_dump_json(indent=2), encoding="utf-8")
            _render_html(reused, html_path)
            return reused, report_path, html_path

    profiles: list[ReferenceProfile] = []
    rights: list[RightsGateRecord] = []
    failures: list[ReferenceFailure] = []
    transcript_paths: dict[str, Path | None] = {}
    for path in fingerprint_paths:
        try:
            profile, gate, transcript_path = _profile(path, metadata)
            profiles.append(profile)
            rights.append(gate)
            transcript_paths[profile.reference_id] = transcript_path
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(ReferenceFailure(input_label=path.name, reason=_safe_error(exc)))
    profiles.sort(key=lambda item: item.reference_id)
    rights.sort(key=lambda item: item.reference_id)
    pairwise = [
        _pair(left, right) for index, left in enumerate(profiles) for right in profiles[index + 1 :]
    ]
    clusters = _clusters(profiles, pairwise, cluster_threshold) if profiles else []
    patterns = _patterns(profiles, rights)
    brief = _brief(
        profiles,
        patterns,
        brand_id=brand_id,
        target_format=target_format,
        topic=topic,
    )
    originality = (
        evaluate_originality_text(
            brief.model_dump_json(exclude={"source_reference_ids"}),
            profiles,
            transcript_paths,
        )
        if brief
        else None
    )
    limitations = [limitation for profile in profiles for limitation in profile.limitations]
    if len(profiles) < 2:
        limitations.append("At least two valid fingerprints are required for comparison.")
    blocked_rights = [gate.reference_id for gate in rights if gate.decision == GateDecision.BLOCK]
    if blocked_rights:
        limitations.append("One or more references lack a valid rights declaration.")
    if not patterns and len(profiles) >= 2:
        limitations.append("No recurring controlled mechanics were supported by two references.")
    blocked = (
        len(profiles) < 2
        or bool(blocked_rights)
        or (originality is not None and originality.decision == GateDecision.BLOCK)
    )
    status = (
        ComparisonStatus.BLOCKED
        if blocked
        else ComparisonStatus.PARTIAL
        if failures or limitations
        else ComparisonStatus.SUCCEEDED
    )
    report = ComparisonReport(
        status=status,
        input_digest=digest,
        reference_count=len(profiles),
        profiles=profiles,
        failures=failures,
        rights_gates=rights,
        pairwise=pairwise,
        clusters=clusters,
        patterns=patterns,
        pattern_brief=brief,
        originality_gate=originality,
        facets=_facets(profiles),
        limitations=list(dict.fromkeys(limitations)),
        ready_for_human_review=not blocked and brief is not None,
    )
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "pattern_library.json").write_text(
        json.dumps(
            {
                "schema_version": "p75.pattern_library.v1",
                "input_digest": digest,
                "patterns": [item.model_dump(mode="json") for item in patterns],
                "human_review_required": True,
                "source_specific_expression_included": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    brief_path = output_dir / "pattern_brief.json"
    originality_path = output_dir / "originality_gate.json"
    if brief:
        brief_path.write_text(brief.model_dump_json(indent=2), encoding="utf-8")
    elif brief_path.exists():
        brief_path.unlink()
    if originality:
        originality_path.write_text(originality.model_dump_json(indent=2), encoding="utf-8")
    elif originality_path.exists():
        originality_path.unlink()
    _render_html(report, html_path)
    return report, report_path, html_path
