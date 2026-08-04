from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.renderers.models import (
    RendererCapabilityRequest,
    RendererHealthRequest,
    RendererRepriceRequest,
)
from src.application.renderers.service import (
    RendererCatalogueError,
    RendererCatalogueService,
    _decimal,
)


class ValidatedRendererCatalogueService(RendererCatalogueService):
    """Production service with evidence-backed health and pricing validation."""

    @staticmethod
    def _estimate_cost(entry: dict[str, Any], request: RendererCapabilityRequest) -> Decimal:
        pricing = dict(entry["pricing"] or {})
        duration = _decimal(request.duration_seconds)
        megapixels = Decimal(request.width * request.height) / Decimal("1000000")
        return (
            _decimal(pricing.get("per_request_usd"))
            + _decimal(pricing.get("base_usd"))
            + _decimal(pricing.get("per_second_usd")) * duration
            + _decimal(pricing.get("per_megapixel_second_usd")) * megapixels * duration
        ).quantize(Decimal("0.000001"))

    def reprice(
        self,
        *,
        entry_id: UUID,
        request: RendererRepriceRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            parent = conn.execute(
                "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s",
                (entry_id,),
            ).fetchone()
        if not parent:
            raise RendererCatalogueError("renderer_entry_not_found")
        if parent["status"] != "active":
            raise RendererCatalogueError("renderer_entry_not_active")

        draft_request = request.model_copy(update={"activate": False})
        created = super().reprice(
            entry_id=entry_id,
            request=draft_request,
            actor=actor,
        )
        child_id = created["entry"]["id"]
        parent_health = str(parent["health_status"])
        if parent_health in {"healthy", "degraded", "unavailable"}:
            self.observe_health(
                entry_id=child_id,
                request=RendererHealthRequest(
                    status=parent_health,
                    checked_by=actor,
                    details={
                        "source": "repricing_parent_health_carry_forward",
                        "parent_entry_id": str(entry_id),
                    },
                ),
                actor=actor,
            )
        if request.activate:
            return self.activate(entry_id=child_id, actor=actor)
        return self.detail(entry_id=child_id)
