from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.application.campaigns.models import (
    AutopilotPolicyCreateRequest,
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class CampaignError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def canonical_item_fingerprint(item: CampaignItemInput) -> str:
    payload = {
        "title": " ".join(item.title.lower().split()),
        "topic": " ".join(item.topic.lower().split()),
        "format_name": item.format_name.lower(),
        "primary_platform": item.primary_platform,
        "target_platforms": sorted(item.target_platforms),
        "target_duration_seconds": item.target_duration_seconds,
        "short_cut_count": item.short_cut_count,
        "language": item.language.lower(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CampaignService:
    """Database-native campaign control plane through activation.

    This service deliberately stops before final video generation. It creates the
    canonical campaign/version/item records and binds the active pre-generation
    autopilot policy used by later orchestration workers.
    """

    def __init__(self, database: "Database") -> None:
        self.database = database

    def create_campaign(self, request: CampaignCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            self._require_active_brand(conn, request.brand_id)
            existing = conn.execute(
                "SELECT * FROM football_brief.production_campaigns WHERE campaign_key=%s FOR UPDATE",
                (request.campaign_key,),
            ).fetchone()
            if existing:
                if str(existing["brand_id"]) != str(request.brand_id):
                    raise CampaignError("campaign_key_brand_conflict")
                result = self._detail_with_connection(conn, existing["id"])
                result["reused"] = True
                return result

            policy = self._ensure_default_policy(conn, brand_id=request.brand_id, actor=actor)
            campaign = conn.execute(
                """INSERT INTO football_brief.production_campaigns
                   (campaign_key,brand_id,name,description,created_by,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    request.campaign_key,
                    request.brand_id,
                    request.name,
                    request.description,
                    actor,
                    _json(request.metadata),
                ),
            ).fetchone()
            version = conn.execute(
                """INSERT INTO football_brief.production_campaign_versions
                   (campaign_id,version,status,autopilot_policy_id,created_by,metadata)
                   VALUES (%s,1,'draft',%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    campaign["id"],
                    policy["id"],
                    actor,
                    _json({"database_native": True, "final_video_generation_deferred": True}),
                ),
            ).fetchone()
            campaign = conn.execute(
                """UPDATE football_brief.production_campaigns
                   SET current_version_id=%s,updated_at=now()
                   WHERE id=%s RETURNING *""",
                (version["id"], campaign["id"]),
            ).fetchone()
            result = self._detail_with_connection(conn, campaign["id"])
            result["reused"] = False
            return result

    def create_policy(
        self,
        *,
        brand_id: UUID,
        request: AutopilotPolicyCreateRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            self._require_active_brand(conn, brand_id)
            current = conn.execute(
                """SELECT * FROM football_brief.pre_generation_autopilot_policies
                   WHERE brand_id=%s AND active=true
                   ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (brand_id,),
            ).fetchone()
            requested = {
                "policy_key": request.policy_key,
                "minimum_auto_score": float(request.minimum_auto_score),
                "max_auto_corrections": request.max_auto_corrections,
                "automatic_stages": list(request.automatic_stages),
                "hard_block_codes": list(request.hard_block_codes),
                "configuration": request.configuration,
            }
            if current and self._policy_matches(dict(current), requested):
                return {"ok": True, "kind": "p119_autopilot_policy", "reused": True, "policy": dict(current)}
            version = conn.execute(
                """SELECT COALESCE(max(version),0)+1 AS value
                   FROM football_brief.pre_generation_autopilot_policies
                   WHERE brand_id=%s""",
                (brand_id,),
            ).fetchone()["value"]
            if current:
                conn.execute(
                    """UPDATE football_brief.pre_generation_autopilot_policies
                       SET active=false,retired_at=now() WHERE id=%s""",
                    (current["id"],),
                )
            row = conn.execute(
                """INSERT INTO football_brief.pre_generation_autopilot_policies
                   (brand_id,version,policy_key,active,minimum_auto_score,max_auto_corrections,
                    automatic_stages,hard_block_codes,configuration,created_by,activated_at)
                   VALUES (%s,%s,%s,true,%s,%s,%s::text[],%s::text[],%s::jsonb,%s,now())
                   RETURNING *""",
                (
                    brand_id,
                    version,
                    request.policy_key,
                    request.minimum_auto_score,
                    request.max_auto_corrections,
                    list(request.automatic_stages),
                    list(request.hard_block_codes),
                    _json(request.configuration),
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "kind": "p119_autopilot_policy", "reused": False, "policy": dict(row)}

    def policy(self, *, brand_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT * FROM football_brief.pre_generation_autopilot_policies
                   WHERE brand_id=%s AND active=true
                   ORDER BY version DESC LIMIT 1""",
                (brand_id,),
            ).fetchone()
        if row is None:
            raise CampaignError("active_autopilot_policy_not_found")
        return {"ok": True, "kind": "p119_autopilot_policy", "policy": dict(row)}

    def add_items(
        self,
        *,
        campaign_version_id: UUID,
        request: CampaignItemsAddRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            context = self._version_for_update(conn, campaign_version_id)
            if context["version_status"] not in {"draft", "invalid"}:
                raise CampaignError("campaign_version_not_editable")
            maximum = conn.execute(
                """SELECT COALESCE(max(ordinal),0) AS value
                   FROM football_brief.production_campaign_items
                   WHERE campaign_version_id=%s""",
                (campaign_version_id,),
            ).fetchone()["value"]
            rows = []
            for offset, item in enumerate(request.items, start=1):
                rows.append(
                    {
                        "item_key": item.item_key,
                        "ordinal": int(maximum) + offset,
                        "title": item.title,
                        "topic": item.topic,
                        "objective": item.objective,
                        "audience": item.audience,
                        "format_name": item.format_name,
                        "primary_platform": item.primary_platform,
                        "target_platforms": list(item.target_platforms),
                        "target_duration_seconds": item.target_duration_seconds,
                        "short_cut_count": item.short_cut_count,
                        "language": item.language,
                        "scheduled_for": item.scheduled_for.isoformat(),
                        "priority": item.priority,
                        "canonical_fingerprint": canonical_item_fingerprint(item),
                        "metadata": item.metadata,
                    }
                )
            changed = conn.execute(
                """WITH input AS (
                       SELECT * FROM jsonb_to_recordset(%s::jsonb) AS x(
                           item_key text,ordinal integer,title text,topic text,objective text,
                           audience text,format_name text,primary_platform text,target_platforms text[],
                           target_duration_seconds integer,short_cut_count integer,language text,
                           scheduled_for date,priority integer,canonical_fingerprint char(64),metadata jsonb
                       )
                   )
                   INSERT INTO football_brief.production_campaign_items
                   (campaign_version_id,item_key,ordinal,title,topic,objective,audience,format_name,
                    primary_platform,target_platforms,target_duration_seconds,short_cut_count,language,
                    scheduled_for,priority,canonical_fingerprint,state,validation_errors,created_by,metadata)
                   SELECT %s,item_key,ordinal,title,topic,objective,audience,format_name,
                          primary_platform,target_platforms,target_duration_seconds,short_cut_count,language,
                          scheduled_for,priority,canonical_fingerprint,'draft','[]'::jsonb,%s,metadata
                   FROM input
                   ON CONFLICT (campaign_version_id,item_key) DO UPDATE SET
                       title=EXCLUDED.title,
                       topic=EXCLUDED.topic,
                       objective=EXCLUDED.objective,
                       audience=EXCLUDED.audience,
                       format_name=EXCLUDED.format_name,
                       primary_platform=EXCLUDED.primary_platform,
                       target_platforms=EXCLUDED.target_platforms,
                       target_duration_seconds=EXCLUDED.target_duration_seconds,
                       short_cut_count=EXCLUDED.short_cut_count,
                       language=EXCLUDED.language,
                       scheduled_for=EXCLUDED.scheduled_for,
                       priority=EXCLUDED.priority,
                       canonical_fingerprint=EXCLUDED.canonical_fingerprint,
                       state='draft',
                       disposition=NULL,
                       validation_errors='[]'::jsonb,
                       updated_at=now(),
                       metadata=EXCLUDED.metadata
                   WHERE football_brief.production_campaign_items.state IN ('draft','invalid')
                   RETURNING id,item_key,state""",
                (_json(rows), campaign_version_id, actor),
            ).fetchall()
            counts = self._refresh_version_counts(conn, campaign_version_id)
            conn.execute(
                """UPDATE football_brief.production_campaign_versions
                   SET status='draft',validated_at=NULL WHERE id=%s""",
                (campaign_version_id,),
            )
            conn.execute(
                """UPDATE football_brief.production_campaigns
                   SET status='draft',updated_at=now() WHERE id=%s""",
                (context["campaign_id"],),
            )
        return {
            "ok": True,
            "kind": "p119_campaign_items_added",
            "campaign_version_id": str(campaign_version_id),
            "submitted": len(request.items),
            "changed": len(changed),
            "counts": counts,
        }

    def validate_version(self, *, campaign_version_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            context = self._version_for_update(conn, campaign_version_id)
            if context["version_status"] not in {"draft", "invalid", "validated"}:
                raise CampaignError("campaign_version_not_validatable")
            policy = conn.execute(
                """SELECT * FROM football_brief.pre_generation_autopilot_policies
                   WHERE id=%s AND brand_id=%s AND active=true""",
                (context["autopilot_policy_id"], context["brand_id"]),
            ).fetchone()
            brand = conn.execute(
                "SELECT id,active FROM football_brief.brands WHERE id=%s",
                (context["brand_id"],),
            ).fetchone()
            items = conn.execute(
                """SELECT * FROM football_brief.production_campaign_items
                   WHERE campaign_version_id=%s
                   ORDER BY ordinal,id FOR UPDATE""",
                (campaign_version_id,),
            ).fetchall()
            if not items:
                raise CampaignError("campaign_version_has_no_items")
            fingerprint_counts = Counter(str(row["canonical_fingerprint"]) for row in items)
            updates: list[dict[str, Any]] = []
            for row in items:
                errors: list[dict[str, Any]] = []
                if brand is None or not bool(brand["active"]):
                    errors.append({"code": "brand_inactive", "field": "brand_id"})
                if policy is None:
                    errors.append({"code": "active_autopilot_policy_required", "field": "autopilot_policy_id"})
                if fingerprint_counts[str(row["canonical_fingerprint"])] > 1:
                    errors.append({"code": "duplicate_within_campaign", "field": "topic"})
                if row["primary_platform"] not in tuple(row["target_platforms"] or ()):
                    errors.append({"code": "primary_platform_not_targeted", "field": "target_platforms"})
                updates.append(
                    {
                        "id": str(row["id"]),
                        "state": "invalid" if errors else "valid",
                        "validation_errors": errors,
                    }
                )
            conn.execute(
                """WITH input AS (
                       SELECT * FROM jsonb_to_recordset(%s::jsonb) AS x(
                           id uuid,state text,validation_errors jsonb
                       )
                   ), changed AS (
                       UPDATE football_brief.production_campaign_items item
                       SET state=input.state,
                           disposition=NULL,
                           validation_errors=input.validation_errors,
                           updated_at=now()
                       FROM input
                       WHERE item.id=input.id
                       RETURNING item.id,item.state AS to_state
                   )
                   INSERT INTO football_brief.production_campaign_item_events
                   (campaign_item_id,event_type,from_state,to_state,actor,details)
                   SELECT changed.id,'validated',NULL,changed.to_state,%s,
                          jsonb_build_object('campaign_version_id',%s::text)
                   FROM changed""",
                (_json(updates), actor, str(campaign_version_id)),
            )
            counts = self._refresh_version_counts(conn, campaign_version_id)
            valid = counts["item_count"] > 0 and counts["invalid_item_count"] == 0
            version_status = "validated" if valid else "invalid"
            campaign_status = "ready" if valid else "draft"
            conn.execute(
                """UPDATE football_brief.production_campaign_versions
                   SET status=%s,validated_at=CASE WHEN %s THEN now() ELSE NULL END
                   WHERE id=%s""",
                (version_status, valid, campaign_version_id),
            )
            conn.execute(
                """UPDATE football_brief.production_campaigns
                   SET status=%s,updated_at=now() WHERE id=%s""",
                (campaign_status, context["campaign_id"]),
            )
        return {
            "ok": valid,
            "kind": "p119_campaign_version_validation",
            "campaign_version_id": str(campaign_version_id),
            "status": version_status,
            "counts": counts,
        }

    def activate_version(self, *, campaign_version_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            context = self._version_for_update(conn, campaign_version_id)
            if context["version_status"] != "validated":
                raise CampaignError("validated_campaign_version_required")
            policy = conn.execute(
                """SELECT id FROM football_brief.pre_generation_autopilot_policies
                   WHERE id=%s AND brand_id=%s AND active=true""",
                (context["autopilot_policy_id"], context["brand_id"]),
            ).fetchone()
            if policy is None:
                raise CampaignError("active_autopilot_policy_required")
            invalid_count = conn.execute(
                """SELECT count(*) AS value FROM football_brief.production_campaign_items
                   WHERE campaign_version_id=%s AND state<>'valid'""",
                (campaign_version_id,),
            ).fetchone()["value"]
            if int(invalid_count):
                raise CampaignError("all_campaign_items_must_be_valid", details={"invalid_count": int(invalid_count)})
            conn.execute(
                """UPDATE football_brief.production_campaign_versions
                   SET status='superseded',superseded_at=now()
                   WHERE campaign_id=%s AND status='active' AND id<>%s""",
                (context["campaign_id"], campaign_version_id),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_versions
                   SET status='active',activated_at=now() WHERE id=%s""",
                (campaign_version_id,),
            )
            changed = conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='activated',disposition='auto_approved',activated_at=now(),updated_at=now()
                   WHERE campaign_version_id=%s AND state='valid'
                   RETURNING id""",
                (campaign_version_id,),
            ).fetchall()
            if changed:
                conn.execute(
                    """INSERT INTO football_brief.production_campaign_item_events
                       (campaign_item_id,event_type,from_state,to_state,actor,details)
                       SELECT id,'campaign_activated','valid','activated',%s,
                              jsonb_build_object('campaign_version_id',%s::text,'automatic_progression',true)
                       FROM football_brief.production_campaign_items
                       WHERE campaign_version_id=%s AND state='activated'""",
                    (actor, str(campaign_version_id), campaign_version_id),
                )
            conn.execute(
                """UPDATE football_brief.production_campaigns
                   SET status='active',current_version_id=%s,activated_at=COALESCE(activated_at,now()),
                       updated_at=now()
                   WHERE id=%s""",
                (campaign_version_id, context["campaign_id"]),
            )
            result = self._detail_with_connection(conn, context["campaign_id"])
        return {
            "ok": True,
            "kind": "p119_campaign_activated",
            "activated_items": len(changed),
            **result,
        }

    def list_campaigns(self, *, brand_ids: list[UUID] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= int(limit) <= 500:
            raise CampaignError("invalid_campaign_limit")
        conditions = ["true"]
        values: list[Any] = []
        if brand_ids is not None:
            if not brand_ids:
                return []
            conditions.append("c.brand_id = ANY(%s::uuid[])")
            values.append(brand_ids)
        values.append(int(limit))
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT c.*,b.slug AS brand_slug,b.display_name AS brand_name,
                            v.version AS current_version,v.status AS current_version_status,
                            v.item_count,v.valid_item_count,v.invalid_item_count
                     FROM football_brief.production_campaigns c
                     JOIN football_brief.brands b ON b.id=c.brand_id
                     LEFT JOIN football_brief.production_campaign_versions v ON v.id=c.current_version_id
                     WHERE {' AND '.join(conditions)}
                     ORDER BY c.updated_at DESC,c.id
                     LIMIT %s""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def detail(self, campaign_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            return self._detail_with_connection(conn, campaign_id)

    def _detail_with_connection(self, conn: Any, campaign_id: UUID) -> dict[str, Any]:
        campaign = conn.execute(
            """SELECT c.*,b.slug AS brand_slug,b.display_name AS brand_name
               FROM football_brief.production_campaigns c
               JOIN football_brief.brands b ON b.id=c.brand_id
               WHERE c.id=%s""",
            (campaign_id,),
        ).fetchone()
        if campaign is None:
            raise CampaignError("campaign_not_found")
        versions = conn.execute(
            """SELECT v.*,p.policy_key,p.minimum_auto_score,p.max_auto_corrections,
                      p.automatic_stages,p.hard_block_codes
               FROM football_brief.production_campaign_versions v
               JOIN football_brief.pre_generation_autopilot_policies p ON p.id=v.autopilot_policy_id
               WHERE v.campaign_id=%s ORDER BY v.version DESC""",
            (campaign_id,),
        ).fetchall()
        state_counts = conn.execute(
            """SELECT item.state,count(*)::int AS count
               FROM football_brief.production_campaign_items item
               JOIN football_brief.production_campaign_versions v ON v.id=item.campaign_version_id
               WHERE v.campaign_id=%s
               GROUP BY item.state ORDER BY item.state""",
            (campaign_id,),
        ).fetchall()
        return {
            "ok": True,
            "kind": "p119_campaign",
            "campaign": dict(campaign),
            "versions": [dict(row) for row in versions],
            "state_counts": {str(row["state"]): int(row["count"]) for row in state_counts},
        }

    def _ensure_default_policy(self, conn: Any, *, brand_id: UUID, actor: str) -> dict[str, Any]:
        current = conn.execute(
            """SELECT * FROM football_brief.pre_generation_autopilot_policies
               WHERE brand_id=%s AND active=true ORDER BY version DESC LIMIT 1""",
            (brand_id,),
        ).fetchone()
        if current:
            return dict(current)
        row = conn.execute(
            """INSERT INTO football_brief.pre_generation_autopilot_policies
               (brand_id,version,policy_key,active,minimum_auto_score,max_auto_corrections,
                automatic_stages,hard_block_codes,configuration,created_by,activated_at)
               VALUES (%s,1,'default-autopilot',true,70,2,
                       ARRAY['concept','script','sources','narration_plan','scene_plan',
                             'caption_package','final_generation_package']::text[],
                       ARRAY['rights_block','safety_block','territory_block','structural_block',
                             'source_block','budget_block','system_block']::text[],
                       %s::jsonb,%s,now())
               RETURNING *""",
            (
                brand_id,
                _json(
                    {
                        "routine_pre_generation_auto_approval": True,
                        "final_video_generation_deferred": True,
                        "automatic_paid_spend": False,
                        "automatic_public_publishing": False,
                    }
                ),
                actor,
            ),
        ).fetchone()
        return dict(row)

    @staticmethod
    def _policy_matches(current: dict[str, Any], requested: dict[str, Any]) -> bool:
        return (
            str(current["policy_key"]) == requested["policy_key"]
            and float(current["minimum_auto_score"]) == requested["minimum_auto_score"]
            and int(current["max_auto_corrections"]) == requested["max_auto_corrections"]
            and list(current["automatic_stages"] or ()) == requested["automatic_stages"]
            and list(current["hard_block_codes"] or ()) == requested["hard_block_codes"]
            and dict(current["configuration"] or {}) == requested["configuration"]
        )

    def _version_for_update(self, conn: Any, campaign_version_id: UUID) -> dict[str, Any]:
        row = conn.execute(
            """SELECT v.id AS version_id,v.status AS version_status,v.autopilot_policy_id,
                      c.id AS campaign_id,c.brand_id,c.status AS campaign_status
               FROM football_brief.production_campaign_versions v
               JOIN football_brief.production_campaigns c ON c.id=v.campaign_id
               WHERE v.id=%s FOR UPDATE OF v,c""",
            (campaign_version_id,),
        ).fetchone()
        if row is None:
            raise CampaignError("campaign_version_not_found")
        return dict(row)

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if row is None:
            raise CampaignError("operator_inactive_or_missing")

    @staticmethod
    def _require_active_brand(conn: Any, brand_id: UUID) -> None:
        row = conn.execute(
            "SELECT id FROM football_brief.brands WHERE id=%s AND active=true",
            (brand_id,),
        ).fetchone()
        if row is None:
            raise CampaignError("brand_not_found_or_inactive")

    @staticmethod
    def _refresh_version_counts(conn: Any, campaign_version_id: UUID) -> dict[str, int]:
        counts = conn.execute(
            """SELECT count(*)::int AS item_count,
                      count(*) FILTER (WHERE state='valid')::int AS valid_item_count,
                      count(*) FILTER (WHERE state='invalid')::int AS invalid_item_count
               FROM football_brief.production_campaign_items
               WHERE campaign_version_id=%s""",
            (campaign_version_id,),
        ).fetchone()
        payload = {
            "item_count": int(counts["item_count"] or 0),
            "valid_item_count": int(counts["valid_item_count"] or 0),
            "invalid_item_count": int(counts["invalid_item_count"] or 0),
        }
        conn.execute(
            """UPDATE football_brief.production_campaign_versions
               SET item_count=%s,valid_item_count=%s,invalid_item_count=%s
               WHERE id=%s""",
            (
                payload["item_count"],
                payload["valid_item_count"],
                payload["invalid_item_count"],
                campaign_version_id,
            ),
        )
        return payload


__all__ = ["CampaignError", "CampaignService", "canonical_item_fingerprint"]
