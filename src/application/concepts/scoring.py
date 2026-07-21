from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from src.application.concepts.models import CandidateDraft, RiskLevel


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
        "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
        "what", "when", "where", "which", "who", "why", "with", "your",
    }
)


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    kind: str
    similarity: float
    content_id: str | None = None
    candidate_id: str | None = None
    title: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateScore:
    originality: float
    engagement: float
    monetization_fit: float
    policy_risk: float
    feasibility: float
    total: float
    evidence: dict[str, Any]


def normalize_text(value: str) -> str:
    return " ".join(TOKEN_RE.findall(value.lower()))


def concept_fingerprint(*, title: str, hook: str, concept: str) -> str:
    canonical = "\n".join(normalize_text(value) for value in (title, hook, concept))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_tokens(*values: str) -> tuple[str, ...]:
    tokens = {
        token
        for value in values
        for token in TOKEN_RE.findall(value.lower())
        if token not in STOPWORDS and len(token) > 2
    }
    return tuple(sorted(tokens))


def semantic_key(tokens: Iterable[str]) -> str:
    values = tuple(sorted(set(tokens)))
    return hashlib.sha256(" ".join(values).encode("utf-8")).hexdigest()[:32]


def jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def find_duplicate(
    *,
    fingerprint: str,
    tokens: Iterable[str],
    historical_rows: Iterable[dict[str, Any]],
    candidate_rows: Iterable[dict[str, Any]] = (),
    semantic_threshold: float = 0.72,
) -> DuplicateMatch | None:
    token_set = tuple(tokens)
    best: DuplicateMatch | None = None
    for row in historical_rows:
        if str(row.get("concept_fingerprint") or "") == fingerprint:
            return DuplicateMatch(
                kind="exact",
                similarity=1.0,
                content_id=str(row.get("id")),
                title=str(row.get("title") or ""),
            )
        row_tokens = row.get("semantic_tokens") or semantic_tokens(
            str(row.get("title") or ""),
            str(row.get("concept") or ""),
            str(row.get("script") or ""),
        )
        similarity = jaccard_similarity(token_set, row_tokens)
        if similarity >= semantic_threshold and (best is None or similarity > best.similarity):
            best = DuplicateMatch(
                kind="semantic",
                similarity=similarity,
                content_id=str(row.get("id")),
                title=str(row.get("title") or ""),
            )
    for row in candidate_rows:
        if str(row.get("concept_fingerprint") or "") == fingerprint:
            return DuplicateMatch(
                kind="exact",
                similarity=1.0,
                candidate_id=str(row.get("id")),
                title=str(row.get("title") or ""),
            )
        similarity = jaccard_similarity(token_set, row.get("semantic_tokens") or ())
        if similarity >= semantic_threshold and (best is None or similarity > best.similarity):
            best = DuplicateMatch(
                kind="semantic",
                similarity=similarity,
                candidate_id=str(row.get("id")),
                title=str(row.get("title") or ""),
            )
    return best


def score_candidate(
    draft: CandidateDraft,
    *,
    duplicate: DuplicateMatch | None,
    context: dict[str, Any],
) -> CandidateScore:
    originality, originality_reasons = _originality_score(duplicate)
    engagement, engagement_reasons = _engagement_score(draft)
    monetization, monetization_reasons = _monetization_score(draft, context)
    policy_risk, policy_reasons = _policy_risk_score(draft, context)
    feasibility, feasibility_reasons = _feasibility_score(draft, context)
    total = (
        originality * 0.25
        + engagement * 0.25
        + monetization * 0.20
        + feasibility * 0.20
        + (100.0 - policy_risk) * 0.10
    )
    if duplicate:
        total = min(total, 20.0 if duplicate.kind == "semantic" else 5.0)
    evidence = {
        "formula": {
            "originality": 0.25,
            "engagement": 0.25,
            "monetization_fit": 0.20,
            "feasibility": 0.20,
            "inverse_policy_risk": 0.10,
        },
        "originality": originality_reasons,
        "engagement": engagement_reasons,
        "monetization_fit": monetization_reasons,
        "policy_risk": policy_reasons,
        "feasibility": feasibility_reasons,
        "duplicate": None
        if duplicate is None
        else {
            "kind": duplicate.kind,
            "similarity": round(duplicate.similarity, 6),
            "content_id": duplicate.content_id,
            "candidate_id": duplicate.candidate_id,
            "title": duplicate.title,
        },
    }
    return CandidateScore(
        originality=round(originality, 3),
        engagement=round(engagement, 3),
        monetization_fit=round(monetization, 3),
        policy_risk=round(policy_risk, 3),
        feasibility=round(feasibility, 3),
        total=round(max(0.0, min(100.0, total)), 3),
        evidence=evidence,
    )


def _originality_score(duplicate: DuplicateMatch | None) -> tuple[float, list[str]]:
    if duplicate is None:
        return 100.0, ["No exact or semantic match met the configured threshold."]
    if duplicate.kind == "exact":
        return 0.0, ["Canonical title, hook, and concept fingerprint matches an existing record."]
    score = max(0.0, 100.0 * (1.0 - duplicate.similarity))
    return score, [f"Semantic overlap is {duplicate.similarity:.1%}, above the duplicate threshold."]


def _engagement_score(draft: CandidateDraft) -> tuple[float, list[str]]:
    score = 45.0
    reasons: list[str] = []
    hook_words = draft.hook.split()
    if 7 <= len(hook_words) <= 24:
        score += 15
        reasons.append("Hook length is concise enough for an opening beat.")
    if any(mark in draft.hook for mark in ("?", ":", "—")):
        score += 8
        reasons.append("Hook contains a clear curiosity or contrast marker.")
    concrete_tokens = semantic_tokens(draft.title, draft.hook)
    specificity = min(15.0, math.log2(max(2, len(concrete_tokens))) * 4.0)
    score += specificity
    reasons.append(f"Title and hook contain {len(concrete_tokens)} nontrivial tokens.")
    if len(draft.concept.split()) >= 45:
        score += 10
        reasons.append("Concept includes enough structure for multiple retention beats.")
    if draft.format in {"vertical_short", "reel", "short", "carousel"}:
        score += 5
        reasons.append("Format supports a fast, platform-native entry point.")
    return min(100.0, score), reasons


def _monetization_score(draft: CandidateDraft, context: dict[str, Any]) -> tuple[float, list[str]]:
    score = 40.0
    reasons: list[str] = []
    goal = normalize_text(str(context.get("monetization_goal") or ""))
    candidate_text = normalize_text(f"{draft.title} {draft.hook} {draft.concept} {draft.rationale}")
    goal_tokens = semantic_tokens(goal)
    overlap = jaccard_similarity(goal_tokens, semantic_tokens(candidate_text)) if goal_tokens else 0.0
    score += min(30.0, overlap * 100.0)
    if goal_tokens:
        reasons.append(f"Concept overlaps {overlap:.1%} with the configured monetization goal vocabulary.")
    else:
        reasons.append("No explicit monetization goal was configured; neutral baseline applied.")
    if any(token in candidate_text for token in ("takeaway", "checklist", "decision", "guide", "compare")):
        score += 15
        reasons.append("Concept has a practical value or conversion bridge.")
    if draft.recommended_route == "local":
        score += 10
        reasons.append("Local production route protects unit economics.")
    return min(100.0, score), reasons


def _policy_risk_score(draft: CandidateDraft, context: dict[str, Any]) -> tuple[float, list[str]]:
    base = {RiskLevel.LOW: 15.0, RiskLevel.MEDIUM: 45.0, RiskLevel.HIGH: 75.0}[draft.factual_risk]
    reasons = [f"Base factual risk is {draft.factual_risk.value}."]
    if len(draft.required_research) >= 2:
        base -= 8
        reasons.append("Two or more explicit research tasks reduce unmanaged factual risk.")
    if len(draft.source_requirements) >= 2:
        base -= 7
        reasons.append("Multiple source requirements improve verification coverage.")
    restrictions = normalize_text(str(context.get("content_restrictions") or ""))
    candidate = normalize_text(f"{draft.title} {draft.hook} {draft.concept}")
    overlap = set(semantic_tokens(restrictions)) & set(semantic_tokens(candidate))
    if overlap:
        base += min(20.0, len(overlap) * 5.0)
        reasons.append(f"Candidate overlaps configured restriction terms: {', '.join(sorted(overlap))}.")
    return max(0.0, min(100.0, base)), reasons


def _feasibility_score(draft: CandidateDraft, context: dict[str, Any]) -> tuple[float, list[str]]:
    score = {RiskLevel.LOW: 92.0, RiskLevel.MEDIUM: 72.0, RiskLevel.HIGH: 48.0}[draft.production_complexity]
    reasons = [f"Production complexity is {draft.production_complexity.value}."]
    budget = context.get("budget") or {}
    per_content = Decimal(str(budget.get("per_content_usd", 0) or 0))
    estimated = Decimal(str(draft.estimated_cost_usd))
    if estimated == 0:
        score += 8
        reasons.append("Estimated direct generation cost is zero.")
    elif per_content > 0:
        if estimated <= per_content:
            score += 8
            reasons.append("Estimated cost is within the configured per-content budget.")
        else:
            overage = float((estimated - per_content) / per_content)
            score -= min(35.0, overage * 35.0)
            reasons.append("Estimated cost exceeds the configured per-content budget.")
    if draft.recommended_route == "managed":
        score -= 12
        reasons.append("Managed-provider dependency reduces local feasibility.")
    return max(0.0, min(100.0, score)), reasons
