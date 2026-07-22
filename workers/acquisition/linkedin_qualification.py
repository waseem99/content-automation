from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


GENUINE_LABEL: Final = "Genuine opportunity — win potential unverified"
DEFAULT_OWNER: Final = "Waseem"
LOCAL_QUEUE: Final = "local_only"


class OpportunityDisposition(StrEnum):
    NEEDS_RESEARCH = "needs_research"
    NOT_OPPORTUNITY = "not_opportunity"
    INDIVIDUAL_HIRING = "individual_hiring"


@dataclass(frozen=True, slots=True)
class LinkedInPostSignal:
    text: str
    original_author: str | None = None
    interaction_actor: str | None = None
    canonical_post_url: str | None = None
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class LinkedInOpportunityDecision:
    disposition: OpportunityDisposition
    status_label: str
    queue: str
    owner: str
    is_genuine_opportunity: bool
    is_job_vacancy: bool
    matched_services: tuple[str, ...]
    reason_codes: tuple[str, ...]
    original_author: str | None
    interaction_actor: str | None
    canonical_post_url: str | None
    source_url: str | None


_BUYER_INTENT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\blooking\s+for\b",
        r"\bseeking\b",
        r"\bneed(?:ed|ing|s)?\b",
        r"\brequir(?:e|ed|es|ing)\b",
        r"\bsearching\s+for\b",
        r"\bcan\s+(?:anyone|someone)\s+recommend\b",
        r"\brecommend(?:ation|ations)?\s+for\b",
        r"\binvit(?:e|es|ing)\s+(?:agencies|vendors|partners|proposals|eois)\b",
        r"\brequest\s+for\s+proposal(?:s)?\b",
        r"\brfp\b",
        r"\bexpression\s+of\s+interest\b",
        r"\beoi\b",
        r"\boutsourc(?:e|ing)\b",
        r"\bappoint(?:ing)?\s+(?:an?\s+)?(?:agency|vendor|partner)\b",
        r"\bhir(?:e|ing)\s+(?:an?\s+)?(?:agency|vendor|studio|company|partner)\b",
    )
)

_AGENCY_ENTITY_PATTERN: Final = re.compile(
    r"\b(?:agency|agencies|vendor|vendors|service\s+provider|service\s+providers|"
    r"studio|studios|production\s+house|production\s+company|creative\s+partner|"
    r"marketing\s+partner|digital\s+partner)\b",
    re.IGNORECASE,
)

_INDIVIDUAL_ROLE_PATTERN: Final = re.compile(
    r"\b(?:manager|executive|specialist|officer|intern|internship|employee|candidate|"
    r"designer|animator|editor|videographer|content\s+writer|copywriter|developer|"
    r"coordinator|strategist)\b",
    re.IGNORECASE,
)

_JOB_PATTERN: Final = re.compile(
    r"\b(?:job\s+opening|job\s+vacancy|vacancy|we(?:'re|\s+are)\s+hiring|"
    r"hiring\s+for|full[-\s]?time|part[-\s]?time|salary|send\s+(?:your\s+)?cv|"
    r"send\s+(?:your\s+)?resume|apply\s+(?:now|here|via)|join\s+our\s+team|"
    r"career\s+opportunity|employment)\b",
    re.IGNORECASE,
)

_PROMOTIONAL_PATTERN: Final = re.compile(
    r"\b(?:we\s+offer|our\s+services|we\s+specialize|we\s+help\s+brands|"
    r"contact\s+us|book\s+a\s+call|check\s+out\s+our|proud\s+to\s+announce|"
    r"won\s+an\s+award)\b",
    re.IGNORECASE,
)

_SERVICE_PATTERNS: Final[tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]] = (
    (
        "digital_marketing",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bdigital\s+marketing\b",
                r"\bdigital\s+agency\b",
                r"\bperformance\s+marketing\b",
                r"\bpaid\s+media\b",
                r"\bmedia\s+buying\b",
            )
        ),
    ),
    (
        "social_media",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bsocial\s+media(?:\s+management|\s+marketing|\s+strategy)?\b",
                r"\bcommunity\s+management\b",
                r"\bsocial\s+content\b",
            )
        ),
    ),
    (
        "content_production",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bcontent\s+(?:creation|production|strategy|development)\b",
                r"\bcreative\s+content\b",
                r"\bbranded\s+content\b",
            )
        ),
    ),
    (
        "animation",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\banimation(?:s)?\b",
                r"\bmotion\s+graphics?\b",
                r"\b3d\s+animation\b",
                r"\b2d\s+animation\b",
            )
        ),
    ),
    (
        "video_production",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bvideo\s+production\b",
                r"\bvideo\s+content\b",
                r"\bvideo\s+editing\b",
                r"\bcommercial\s+production\b",
                r"\bfilm\s+production\b",
            )
        ),
    ),
    (
        "ai_creative",
        tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bai[-\s]?powered\s+(?:video|videos|content|creative|creatives)\b",
                r"\bai\s+(?:video|videos|content|creative|creatives)\b",
                r"\bgenerative\s+ai\s+(?:video|content|creative|creatives)\b",
                r"\bsynthetic\s+media\b",
            )
        ),
    ),
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _matched_services(text: str) -> tuple[str, ...]:
    matches: list[str] = []
    for service, patterns in _SERVICE_PATTERNS:
        if _matches_any(text, patterns):
            matches.append(service)
    return tuple(matches)


def classify_linkedin_opportunity(
    signal: LinkedInPostSignal,
    *,
    owner: str = DEFAULT_OWNER,
) -> LinkedInOpportunityDecision:
    """Classify an agency-service LinkedIn signal without contacting or publishing.

    The classifier is intentionally conservative. A genuine signal requires a supported
    service plus buyer intent. Ordinary employment posts, self-promotion, and generic
    discussion remain outside the agency opportunity queue.
    """

    text = _normalize_text(signal.text)
    services = _matched_services(text)
    has_buyer_intent = _matches_any(text, _BUYER_INTENT_PATTERNS)
    has_agency_entity = bool(_AGENCY_ENTITY_PATTERN.search(text))
    has_job_language = bool(_JOB_PATTERN.search(text))
    has_individual_role = bool(_INDIVIDUAL_ROLE_PATTERN.search(text))
    has_promotional_language = bool(_PROMOTIONAL_PATTERN.search(text))

    agency_hiring_override = bool(
        re.search(
            r"\bhir(?:e|ing)\s+(?:an?\s+)?(?:agency|vendor|studio|company|partner)\b",
            text,
            re.IGNORECASE,
        )
    )
    is_job_vacancy = has_job_language and has_individual_role and not agency_hiring_override

    reason_codes: list[str] = []
    if services:
        reason_codes.append("supported_agency_service")
    if has_buyer_intent:
        reason_codes.append("buyer_intent")
    if has_agency_entity:
        reason_codes.append("agency_or_vendor_requested")
    if is_job_vacancy:
        reason_codes.append("individual_job_vacancy")
    if has_promotional_language and not has_buyer_intent:
        reason_codes.append("seller_self_promotion")

    is_genuine = bool(services and has_buyer_intent and not is_job_vacancy)
    if has_promotional_language and not has_buyer_intent:
        is_genuine = False

    if is_genuine:
        disposition = OpportunityDisposition.NEEDS_RESEARCH
        status_label = GENUINE_LABEL
    elif is_job_vacancy:
        disposition = OpportunityDisposition.INDIVIDUAL_HIRING
        status_label = "Not an agency opportunity — individual hiring"
    else:
        disposition = OpportunityDisposition.NOT_OPPORTUNITY
        status_label = "Not qualified as an agency opportunity"
        if not services:
            reason_codes.append("no_supported_service")
        if not has_buyer_intent:
            reason_codes.append("no_buyer_intent")

    return LinkedInOpportunityDecision(
        disposition=disposition,
        status_label=status_label,
        queue=LOCAL_QUEUE,
        owner=owner,
        is_genuine_opportunity=is_genuine,
        is_job_vacancy=is_job_vacancy,
        matched_services=services,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        original_author=signal.original_author,
        interaction_actor=signal.interaction_actor,
        canonical_post_url=signal.canonical_post_url,
        source_url=signal.source_url,
    )
