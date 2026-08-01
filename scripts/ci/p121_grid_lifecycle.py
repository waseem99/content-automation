from __future__ import annotations

import hashlib
from datetime import date
from uuid import UUID

from src.application.campaigns.models import (
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.pre_generation.query_service import CampaignQueryService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def run() -> None:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            brand = conn.execute(
                "SELECT id,primary_platform FROM football_brief.brands WHERE active=true ORDER BY slug LIMIT 1"
            ).fetchone()
        assert brand
        campaign_service = ValidatedCampaignService(database)
        created = campaign_service.create_campaign(
            CampaignCreateRequest(
                campaign_key="p121-grid-lifecycle",
                brand_id=UUID(str(brand["id"])),
                name="P121 Campaign Grid Lifecycle",
            ),
            actor="local-admin",
        )
        campaign_id = UUID(str(created["campaign"]["id"]))
        version_id = UUID(str(created["versions"][0]["id"]))
        primary = str(brand["primary_platform"])
        items = [
            CampaignItemInput(
                item_key=f"grid-{index:04d}",
                title=f"Campaign grid record {index:04d}",
                topic=f"Unique campaign operations topic {index:04d}",
                objective="Prove database-backed filtering, sorting and cursor navigation.",
                audience="Internal operations team",
                primary_platform=primary,
                target_platforms=[primary],
                target_duration_seconds=45,
                scheduled_for=date(2026, 8, (index % 28) + 1),
                priority=index % 100,
                metadata={"grid_lifecycle": True, "index": index},
            )
            for index in range(1, 1201)
        ]
        campaign_service.add_items(
            campaign_version_id=version_id,
            request=CampaignItemsAddRequest(items=items),
            actor="local-admin",
        )
        validation = campaign_service.validate_version(
            campaign_version_id=version_id,
            actor="local-admin",
        )
        assert validation["ok"] is True
        campaign_service.activate_version(
            campaign_version_id=version_id,
            actor="local-admin",
        )

        query = CampaignQueryService(database)
        ensured = query.ensure_runs(campaign_id=campaign_id, actor="local-admin")
        assert ensured["created"] == 1200

        first = query.query_items(campaign_id=campaign_id, limit=500)
        assert first["filtered_count"] == 1200
        assert first["page_count"] == 500
        assert first["has_more"] is True
        assert first["next_cursor"]
        first_ids = {row["id"] for row in first["items"]}

        second = query.query_items(
            campaign_id=campaign_id,
            cursor=first["next_cursor"],
            limit=500,
        )
        assert second["page_count"] == 500
        assert second["has_more"] is True
        second_ids = {row["id"] for row in second["items"]}
        assert first_ids.isdisjoint(second_ids)

        third = query.query_items(
            campaign_id=campaign_id,
            cursor=second["next_cursor"],
            limit=500,
        )
        assert third["page_count"] == 200
        assert third["has_more"] is False
        assert first_ids.isdisjoint({row["id"] for row in third["items"]})
        assert second_ids.isdisjoint({row["id"] for row in third["items"]})

        searched = query.query_items(
            campaign_id=campaign_id,
            query="record 0777",
            limit=100,
        )
        assert searched["filtered_count"] == 1
        assert searched["items"][0]["item_key"] == "grid-0777"

        priority = query.query_items(
            campaign_id=campaign_id,
            sort="priority",
            direction="desc",
            limit=100,
        )
        priorities = [int(row["priority"]) for row in priority["items"]]
        assert priorities == sorted(priorities, reverse=True)

        with database.transaction() as conn:
            selected = conn.execute(
                """SELECT item.id AS item_id,run.id AS run_id
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   WHERE item.campaign_version_id=%s
                   ORDER BY item.ordinal LIMIT 7 FOR UPDATE OF item,run""",
                (version_id,),
            ).fetchall()
            item_ids = [row["item_id"] for row in selected]
            run_ids = [row["run_id"] for row in selected]
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='human_exception',disposition='human_exception',updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (item_ids,),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='human_exception',last_error_code='continuity_plan_defect',
                       last_error_detail='{"synthetic":true}'::jsonb,updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (run_ids,),
            )
            for ordinal, row in enumerate(selected, start=1):
                fingerprint = hashlib.sha256(
                    f"continuity-plan-defect-{ordinal}".encode("utf-8")
                ).hexdigest()
                conn.execute(
                    """INSERT INTO football_brief.pre_generation_exceptions
                       (run_id,campaign_item_id,exception_code,category,severity,status,
                        rule_version,fingerprint,details)
                       VALUES (%s,%s,'continuity_plan_defect','continuity','human_exception',
                               'open','p121-grid-v1',%s,'{"synthetic":true}'::jsonb)""",
                    (row["run_id"], row["item_id"], fingerprint),
                )

        filtered = query.query_items(
            campaign_id=campaign_id,
            states=["human_exception"],
            exception_codes=["continuity_plan_defect"],
            limit=100,
        )
        assert filtered["filtered_count"] == 7
        assert filtered["groups"] == {"human_exception": 7}
        assert all(row["open_exception_count"] == 1 for row in filtered["items"])

        retried = query.retry_matching(
            campaign_id=campaign_id,
            query=None,
            states=["human_exception"],
            exception_codes=["continuity_plan_defect"],
            actor="local-admin",
            maximum=20_000,
        )
        assert retried["count"] == 7
        after = query.query_items(
            campaign_id=campaign_id,
            states=["auto_progressing"],
            limit=100,
        )
        assert after["filtered_count"] == 7
        with database.connection() as conn:
            open_count = conn.execute(
                """SELECT count(*)::int AS value
                   FROM football_brief.pre_generation_exceptions
                   WHERE campaign_item_id=ANY(%s::uuid[]) AND status='open'""",
                (item_ids,),
            ).fetchone()["value"]
            action = conn.execute(
                """SELECT * FROM football_brief.production_campaign_actions
                   WHERE id=%s""",
                (UUID(str(retried["action_id"])),),
            ).fetchone()
        assert open_count == 0
        assert action["requested_count"] == 7
        assert action["succeeded_count"] == 7
    finally:
        database.close()


if __name__ == "__main__":
    run()
