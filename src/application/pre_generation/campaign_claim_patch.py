from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from src.application.pre_generation.service import PreGenerationError, PreGenerationService


_ORIGINAL_CLAIM = PreGenerationService.claim


def _campaign_scoped_claim(
    self: PreGenerationService,
    *,
    owner: str,
    limit: int = 25,
    lease_seconds: int = 300,
    campaign_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Claim the canonical queue, optionally restricted to one campaign.

    Existing worker callers omit ``campaign_id`` and retain the original claim
    implementation byte-for-byte. Campaign-scoped acceptance claims exclude
    waiting runs so an earlier batch cannot be reclaimed while untouched queued
    items still remain. The acceptance runner explicitly requeues all items after
    scripts and evidence are prepared.
    """

    if campaign_id is None:
        return _ORIGINAL_CLAIM(
            self,
            owner=owner,
            limit=limit,
            lease_seconds=lease_seconds,
        )
    if not 1 <= limit <= 500:
        raise PreGenerationError("invalid_claim_limit")
    if not 30 <= lease_seconds <= 3600:
        raise PreGenerationError("invalid_lease_seconds")
    token = uuid4()
    with self.database.transaction() as conn:
        rows = conn.execute(
            """WITH candidates AS (
                   SELECT run.id
                   FROM football_brief.pre_generation_runs run
                   JOIN football_brief.production_campaign_items item
                     ON item.id=run.campaign_item_id
                   JOIN football_brief.production_campaign_versions version
                     ON version.id=item.campaign_version_id
                   JOIN football_brief.production_campaigns campaign
                     ON campaign.id=version.campaign_id
                   WHERE run.status IN ('queued','running')
                     AND run.next_attempt_at<=now()
                     AND (run.lease_expires_at IS NULL OR run.lease_expires_at<now())
                     AND campaign.status='active'
                     AND version.status='active'
                     AND item.state IN ('activated','auto_progressing')
                     AND campaign.id=%s
                   ORDER BY item.priority DESC,item.ordinal,run.created_at
                   FOR UPDATE OF run SKIP LOCKED
                   LIMIT %s
               )
               UPDATE football_brief.pre_generation_runs run
               SET status='running',lease_owner=%s,lease_token=%s,
                   lease_expires_at=now()+(%s || ' seconds')::interval,
                   started_at=COALESCE(started_at,now()),updated_at=now()
               FROM candidates
               WHERE run.id=candidates.id
               RETURNING run.*""",
            (campaign_id, limit, owner, token, lease_seconds),
        ).fetchall()
    return [dict(row) for row in rows]


def install_campaign_scoped_claim_patch() -> None:
    if getattr(PreGenerationService, "_campaign_scoped_claim_installed", False):
        return
    PreGenerationService.claim = _campaign_scoped_claim
    PreGenerationService._campaign_scoped_claim_installed = True


__all__ = ["install_campaign_scoped_claim_patch"]
