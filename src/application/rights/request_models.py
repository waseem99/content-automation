from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from src.application.rights.enums import RightsGatePoint, RightsPlatform
from src.domain.base import FrozenRecord


class RightsGateRequest(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID | None = None
    gate_point: RightsGatePoint
    asset_ids: tuple[UUID, ...]
    platform: RightsPlatform
    territory: str
    campaign: str | None = None
    commercial_use: bool = False
    editorial_use: bool = False
    modification: bool = False
    synthetic_edit: bool = False
    supplied_attribution: dict[UUID, str] = Field(default_factory=dict)
    evaluated_by: str = Field(min_length=1)

    @field_validator("asset_ids")
    @classmethod
    def validate_assets(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value:
            raise ValueError("At least one asset is required")
        if len(set(value)) != len(value):
            raise ValueError("Duplicate asset IDs are not allowed")
        return value

    @field_validator("territory")
    @classmethod
    def normalize_territory(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.lower() == "worldwide":
            return "worldwide"
        normalized = normalized.upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("Territory must be an ISO alpha-2 code or worldwide")
        return normalized

    @field_validator("campaign")
    @classmethod
    def normalize_campaign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    def requested_uses(self) -> tuple[str, ...]:
        result: list[str] = []
        if self.commercial_use:
            result.append("commercial")
        if self.editorial_use:
            result.append("editorial")
        if self.modification:
            result.append("modification")
        if self.synthetic_edit:
            result.append("synthetic_edit")
        return tuple(result)
