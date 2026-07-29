from __future__ import annotations

import re
from typing import Any

from src.application.video_pilot.models import DistributionScope, ModelUsePreflightRequest


_TERRITORY_ALIASES = {
    "eu": "european_union",
    "europeanunion": "european_union",
    "european_union": "european_union",
    "uk": "united_kingdom",
    "unitedkingdom": "united_kingdom",
    "united_kingdom": "united_kingdom",
    "southkorea": "south_korea",
    "south_korea": "south_korea",
    "republicofkorea": "south_korea",
}


def territory_key(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())
    return _TERRITORY_ALIASES.get(compact, compact)


def evaluate_model_policy(policy: dict[str, Any], request: ModelUsePreflightRequest) -> dict[str, Any]:
    reasons: list[str] = []
    scope = request.distribution_scope.value
    allowed_scopes = {str(value) for value in policy.get("allowed_use_scopes") or ()}
    prohibited = {territory_key(value) for value in policy.get("prohibited_territories") or ()}
    requested = {territory_key(value) for value in request.release_territories}

    if not bool(policy.get("commercial_use_allowed")):
        reasons.append("commercial_use_not_allowed")
    if scope not in allowed_scopes:
        reasons.append("distribution_scope_not_allowed")
    if request.distribution_scope == DistributionScope.TERRITORY_LIMITED and not requested:
        reasons.append("release_territories_required")

    intersection = sorted(prohibited.intersection(requested))
    if intersection:
        reasons.append("release_territory_prohibited")
    if request.distribution_scope == DistributionScope.GLOBAL_PUBLIC and prohibited:
        reasons.append("global_public_distribution_reaches_prohibited_territories")

    return {
        "ok": True,
        "kind": "video_model_use_preflight",
        "accepted": not reasons,
        "rejection_reasons": reasons,
        "provider_key": policy["provider_key"],
        "model_key": policy["model_key"],
        "policy_id": str(policy["id"]),
        "policy_version": int(policy["version"]),
        "policy_evidence_digest": policy["evidence_digest"],
        "distribution_scope": scope,
        "release_territories": list(request.release_territories),
        "prohibited_territory_matches": intersection,
        "policy_requires_written_clearance": bool(policy.get("requires_written_clearance")),
        "clearance_process": "activate_a_reviewed_child_policy_version",
    }
