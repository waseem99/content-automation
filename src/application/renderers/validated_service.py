from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.renderers.models import (
    RendererHealthRequest,
    RendererRepriceRequest,
)
from src.application.renderers.service import (
    RendererCatalogueError,
    RendererCatalogueService,
)


class ValidatedRendererCatalogueService(RendererCatalogueService):
    """Production service with evidence-backed health carry-forward on repricing."""

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
