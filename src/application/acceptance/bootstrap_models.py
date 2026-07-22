from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.application.acceptance.models import ProductionMode


_RESERVED_POLICY_KEYS = {
    "bootstrap_request_sha256",
    "bootstrap_kind",
    "bootstrap_item_count",
}


class PilotBootstrapItem(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    production_mode: ProductionMode
    live_delivery_evidence_required: bool = False


class PilotBootstrapRequest(BaseModel):
    pilot_key: str = Field(
        min_length=8,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]+$",
    )
    acceptance_policy: dict[str, Any] = Field(default_factory=dict)
    items: tuple[PilotBootstrapItem, ...]

    @field_validator("pilot_key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_exact_bootstrap_scope(self) -> "PilotBootstrapRequest":
        if len(self.items) != 4:
            raise ValueError("bootstrap requires exactly four items")
        content_ids = [item.portfolio_content_id for item in self.items]
        if len(set(content_ids)) != 4:
            raise ValueError("bootstrap content IDs must be unique")
        identities = [
            (item.portfolio_content_id, item.content_version)
            for item in self.items
        ]
        if len(set(identities)) != 4:
            raise ValueError("bootstrap content versions must be unique")
        if sum(item.live_delivery_evidence_required for item in self.items) != 1:
            raise ValueError(
                "bootstrap requires exactly one external live-result evidence item"
            )
        reserved = sorted(_RESERVED_POLICY_KEYS.intersection(self.acceptance_policy))
        if reserved:
            raise ValueError(
                "acceptance_policy contains reserved bootstrap keys: "
                + ", ".join(reserved)
            )
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "pilot_key": self.pilot_key,
            "acceptance_policy": self.acceptance_policy,
            "items": sorted(
                [item.model_dump(mode="json") for item in self.items],
                key=lambda item: (
                    item["portfolio_content_id"],
                    item["content_version"],
                    item["production_mode"],
                ),
            ),
        }


__all__ = ["PilotBootstrapItem", "PilotBootstrapRequest"]
