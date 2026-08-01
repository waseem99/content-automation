from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.campaigns.models import AutopilotPolicyCreateRequest
from src.application.campaigns.service import CampaignService


class ValidatedCampaignService(CampaignService):
    """Campaign service with safe policy-version progression.

    Active campaigns retain their immutable pinned policy. Draft, invalid and
    validated campaign versions adopt a newly activated brand policy and return
    to draft validation so they cannot be stranded on a retired policy.
    """

    def create_policy(
        self,
        *,
        brand_id: UUID,
        request: AutopilotPolicyCreateRequest,
        actor: str,
    ) -> dict[str, Any]:
        result = super().create_policy(
            brand_id=brand_id,
            request=request,
            actor=actor,
        )
        if bool(result.get("reused")):
            return result

        policy = dict(result["policy"])
        with self.database.transaction() as conn:
            versions = conn.execute(
                """UPDATE football_brief.production_campaign_versions v
                   SET autopilot_policy_id=%s,
                       status='draft',
                       validated_at=NULL,
                       metadata=v.metadata || %s::jsonb
                   FROM football_brief.production_campaigns c
                   WHERE c.id=v.campaign_id
                     AND c.brand_id=%s
                     AND v.status IN ('draft','invalid','validated')
                   RETURNING v.id,v.campaign_id""",
                (
                    policy["id"],
                    '{"autopilot_policy_rebound":true}',
                    brand_id,
                ),
            ).fetchall()
            version_ids = [row["id"] for row in versions]
            campaign_ids = sorted({row["campaign_id"] for row in versions})
            if version_ids:
                conn.execute(
                    """UPDATE football_brief.production_campaign_items
                       SET state='draft',disposition=NULL,validation_errors='[]'::jsonb,updated_at=now()
                       WHERE campaign_version_id = ANY(%s::uuid[])
                         AND state IN ('valid','invalid')""",
                    (version_ids,),
                )
            if campaign_ids:
                conn.execute(
                    """UPDATE football_brief.production_campaigns
                       SET status='draft',updated_at=now()
                       WHERE id = ANY(%s::uuid[])""",
                    (campaign_ids,),
                )
        return {
            **result,
            "rebound_campaign_versions": len(version_ids),
            "rebound_campaigns": len(campaign_ids),
        }


__all__ = ["ValidatedCampaignService"]
