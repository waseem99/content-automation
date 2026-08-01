from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.pre_generation.service import PreGenerationService


def _validated_ensure_runs(
    self: PreGenerationService,
    *,
    campaign_id: UUID | None = None,
    actor: str,
) -> dict[str, Any]:
    """Create durable campaign runs with explicitly typed JSON metadata inputs.

    PostgreSQL cannot infer a bare bound parameter type inside
    ``jsonb_build_object``. Casting the operator ID to text keeps the query
    deterministic across psycopg/PostgreSQL versions and every caller.
    """

    with self.database.transaction() as conn:
        self._require_operator(conn, actor)
        conditions = [
            "item.state='activated'",
            "version.status='active'",
            "campaign.status='active'",
        ]
        values: list[Any] = []
        if campaign_id is not None:
            conditions.append("campaign.id=%s")
            values.append(campaign_id)
        inserted = conn.execute(
            f"""INSERT INTO football_brief.pre_generation_runs
                (campaign_item_id,autopilot_policy_id,status,current_stage,metadata)
                SELECT item.id,version.autopilot_policy_id,'queued','content_expansion',
                       jsonb_build_object(
                           'created_by',%s::text,
                           'campaign_id',campaign.id::text
                       )
                FROM football_brief.production_campaign_items item
                JOIN football_brief.production_campaign_versions version
                  ON version.id=item.campaign_version_id
                JOIN football_brief.production_campaigns campaign
                  ON campaign.id=version.campaign_id
                WHERE {' AND '.join(conditions)}
                ON CONFLICT (campaign_item_id) DO NOTHING
                RETURNING id""",
            (actor, *values),
        ).fetchall()
    return {
        "ok": True,
        "kind": "pre_generation_runs_ensured",
        "campaign_id": str(campaign_id) if campaign_id else None,
        "created": len(inserted),
    }


def install_pre_generation_runtime_patch() -> None:
    if getattr(PreGenerationService, "_typed_ensure_runs_installed", False):
        return
    PreGenerationService.ensure_runs = _validated_ensure_runs
    PreGenerationService._typed_ensure_runs_installed = True


__all__ = ["install_pre_generation_runtime_patch"]
