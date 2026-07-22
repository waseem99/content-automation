from __future__ import annotations

import psycopg
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import (
    PilotAcceptRequest,
    PilotCreateRequest,
    PilotItemRequest,
    PilotRetireRequest,
    ProductionMode,
    SignoffDecision,
    SignoffRequest,
    SignoffRole,
)
from src.application.acceptance.validated_service import p100_runbook_sha256
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def seed_pilot_contents(database, seeded) -> dict[str, object]:
    with database.transaction() as conn:
        publisher_user = conn.execute(
            """INSERT INTO football_brief.operator_users
               (operator_id,display_name,created_by)
               VALUES ('publisher.p100','P100 Publisher','admin.one')
               RETURNING id"""
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.operator_user_roles
               (operator_user_id,role,assigned_by)
               VALUES (%s,'publisher','admin.one')""",
            (publisher_user["id"],),
        )

        result: dict[str, object] = {
            "publisher": "publisher.p100",
            "brands": {},
            "plans": {},
            "contents": {},
        }
        for slug, name, marker in (
            ("animal-x", "Animal X", "a"),
            ("rawr-nation", "Rawr Nation", "b"),
        ):
            brand = conn.execute(
                """INSERT INTO football_brief.brands
                   (slug,display_name,niche,primary_platform,content_mode,monthly_target)
                   VALUES (%s,%s,'Animal education','youtube_shorts','video',20)
                   RETURNING id""",
                (slug, name),
            ).fetchone()
            plan = conn.execute(
                """INSERT INTO football_brief.monthly_content_plans
                   (brand_id,month_start,target_count,status,created_by)
                   VALUES (%s,DATE '2026-11-01',2,'draft','admin.one')
                   RETURNING id""",
                (brand["id"],),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,'admin.one')""",
                (publisher_user["id"], brand["id"]),
            )
            content_rows = []
            for ordinal in (1, 2):
                fingerprint = (marker + str(ordinal)) * 32
                content = conn.execute(
                    """INSERT INTO football_brief.portfolio_content
                       (plan_id,scheduled_for,title,concept,format,concept_fingerprint,semantic_key)
                       VALUES (%s,DATE '2026-11-02',%s,%s,'vertical_short',%s,%s)
                       RETURNING id,version""",
                    (
                        plan["id"],
                        f"{name} pilot item {ordinal}",
                        f"Controlled acceptance pilot concept {ordinal} for {name}.",
                        fingerprint[:64],
                        f"p100-{slug}-{ordinal}",
                    ),
                ).fetchone()
                content_rows.append(dict(content))
            result["brands"][slug] = brand["id"]
            result["plans"][slug] = plan["id"]
            result["contents"][slug] = content_rows
    return result


def test_pilot_scope_blocks_direct_pass_and_revises_through_retirement(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_pilot_contents(p89_database, p89_seeded)
    service = AcceptancePilotService(p89_database)
    created = service.create(
        PilotCreateRequest(
            pilot_key="p100-controlled-pilot",
            acceptance_policy={"critical_defects_allowed": 0, "major_defects_allowed": 0},
        ),
        actor=p89_seeded["admin"],
    )
    pilot_id = created["pilot"]["id"]

    added = []
    for slug in ("animal-x", "rawr-nation"):
        rows = ready["contents"][slug]
        for index, content in enumerate(rows):
            added.append(
                service.add_item(
                    pilot_id=pilot_id,
                    request=PilotItemRequest(
                        portfolio_content_id=content["id"],
                        content_version=int(content["version"]),
                        production_mode=(
                            ProductionMode.LOCAL_ONLY
                            if index == 0
                            else ProductionMode.MANAGED_RENDER
                        ),
                        live_delivery_evidence_required=(slug == "rawr-nation" and index == 1),
                    ),
                    actor=p89_seeded["admin"],
                )["item"]
            )

    assert len(added) == 4
    with p89_database.transaction() as conn:
        extra = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id,scheduled_for,title,concept,format,concept_fingerprint,semantic_key)
               VALUES (%s,DATE '2026-11-03','Animal X overflow item',
                       'Valid fifth content used to prove the bounded pilot scope.',
                       'vertical_short',%s,'p100-animal-x-overflow')
               RETURNING id,version""",
            (ready["plans"]["animal-x"], "c" * 64),
        ).fetchone()
    with pytest.raises(psycopg.Error, match="two items per brand and four total"):
        with p89_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.acceptance_pilot_items
                   (pilot_id,brand_id,portfolio_content_id,content_version,production_mode,
                    required_revision_stages,created_by)
                   VALUES (%s,%s,%s,%s,'local_only',ARRAY['script','narration','visual'],'admin.one')""",
                (
                    pilot_id,
                    ready["brands"]["animal-x"],
                    extra["id"],
                    int(extra["version"]),
                ),
            )

    service.start(pilot_id=pilot_id, actor=p89_seeded["admin"])
    with pytest.raises(psycopg.Error, match="all content evidence"):
        with p89_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.acceptance_pilot_items SET status='passed' WHERE id=%s",
                (added[0]["id"],),
            )

    with pytest.raises(psycopg.Error, match="four passed items"):
        service.signoff(
            pilot_id=pilot_id,
            request=SignoffRequest(
                role=SignoffRole.ADMIN,
                decision=SignoffDecision.APPROVED,
                rationale="The pilot is not actually ready and this sign-off must be rejected.",
            ),
            actor=p89_seeded["admin"],
        )

    with pytest.raises(psycopg.Error, match="four passed items"):
        service.accept(
            pilot_id=pilot_id,
            request=PilotAcceptRequest(
                production_release_tag="prod-p100-premature-01",
                runbook_sha256=p100_runbook_sha256(),
            ),
            actor=p89_seeded["admin"],
        )

    with p89_database.connection() as conn:
        unchanged = conn.execute(
            """SELECT status,production_release_tag,release_tagged_by,release_tagged_at,
                      runbook_path,runbook_sha256
                 FROM football_brief.acceptance_pilots WHERE id=%s""",
            (pilot_id,),
        ).fetchone()
    assert unchanged["status"] == "running"
    assert unchanged["production_release_tag"] is None
    assert unchanged["release_tagged_by"] is None
    assert unchanged["release_tagged_at"] is None
    assert unchanged["runbook_path"] is None
    assert unchanged["runbook_sha256"] is None

    retired = service.retire(
        pilot_id=pilot_id,
        request=PilotRetireRequest(
            reason="Evidence collection must be repeated on a corrected child pilot."
        ),
        actor=p89_seeded["admin"],
    )
    assert retired["pilot"]["status"] == "retired"

    revised = service.create(
        PilotCreateRequest(
            pilot_key="p100-controlled-pilot",
            acceptance_policy={"critical_defects_allowed": 0, "major_defects_allowed": 0},
        ),
        actor=p89_seeded["admin"],
    )
    assert revised["pilot"]["version"] == 2
    assert revised["pilot"]["parent_pilot_id"] == pilot_id
    assert revised["pilot"]["status"] == "draft"
