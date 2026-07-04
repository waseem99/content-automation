from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.application.rights.enums import RightsDecisionOutcome
from src.application.rights.reason_codes import RightsReasonCode
from src.domain.base import FrozenRecord


class RightsObligations(FrozenRecord):
    attribution_required: bool = False
    attribution_text: str | None = None
    disclosures: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetRightsDecision(FrozenRecord):
    asset_id: UUID
    asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rights_id: UUID | None = None
    outcome: RightsDecisionOutcome
    reason_codes: tuple[RightsReasonCode, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    obligations: RightsObligations = Field(default_factory=RightsObligations)


class RightsGateDecision(FrozenRecord):
    evaluation_id: UUID
    outcome: RightsDecisionOutcome
    asset_decisions: tuple[AssetRightsDecision, ...]
    reason_codes: tuple[RightsReasonCode, ...]
    policy_version: str
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime
