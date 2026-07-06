from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import Field

from src.application.observability.redaction import redact_value
from src.domain.base import FrozenRecord


class StructuredLogContext(FrozenRecord):
    workflow_run_id: UUID | None = None
    stage_execution_id: UUID | None = None
    worker_name: str | None = None
    asset_id: UUID | None = None
    provider: str | None = None
    provider_request_id: str | None = None


class StructuredLogEvent(FrozenRecord):
    event: str = Field(min_length=1)
    level: str = "info"
    context: StructuredLogContext = Field(default_factory=StructuredLogContext)
    payload: dict[str, Any] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "event": self.event,
            "level": self.level,
            "context": self.context.model_dump(mode="json", exclude_none=True),
            "payload": redact_value(self.payload),
        }
        return redact_value(data)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


def log_event(event: str, *, context: StructuredLogContext | None = None, payload: dict[str, Any] | None = None, level: str = "info") -> StructuredLogEvent:
    return StructuredLogEvent(event=event, level=level, context=context or StructuredLogContext(), payload=payload or {})
