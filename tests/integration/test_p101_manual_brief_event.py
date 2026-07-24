from __future__ import annotations

import pytest

from src.operator_api.studio_v2_runtime import StudioV2Service
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def test_manual_brief_transition_records_a_schema_allowed_event(
    p89_database,
    p89_seeded,
) -> None:
    workflow_id = p89_seeded["workflow_one"]
    actor = p89_seeded["admin"]
    brief = {
        "title": "Education: Frequently Misunderstood Question #01",
        "topic": "Explain one misunderstood wildlife question with evidence-led beats.",
        "platform": "facebook",
        "format": "vertical_short",
        "duration_seconds": 45,
        "language": "en-US",
    }

    # Reproduce the Creator Studio path that accepts a saved brief before
    # the first script job is queued. The existing fixture starts at
    # script_draft, so move it back using the workflow's required lock step.
    with p89_database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.production_workflows
               SET current_stage='concept_draft', lock_version=lock_version+1
               WHERE id=%s""",
            (workflow_id,),
        )

    StudioV2Service(p89_database)._accept_manual_brief(
        workflow_id=workflow_id,
        actor=actor,
        brief=brief,
    )

    with p89_database.connection() as conn:
        workflow = conn.execute(
            """SELECT current_stage,lock_version,current_version_id
               FROM football_brief.production_workflows WHERE id=%s""",
            (workflow_id,),
        ).fetchone()
        history = conn.execute(
            """SELECT from_stage,to_stage,event,actor,from_lock_version,to_lock_version
               FROM football_brief.production_workflow_stage_history
               WHERE workflow_id=%s ORDER BY created_at DESC,id DESC LIMIT 1""",
            (workflow_id,),
        ).fetchone()
        version = conn.execute(
            """SELECT snapshot FROM football_brief.production_workflow_versions
               WHERE id=%s""",
            (workflow["current_version_id"],),
        ).fetchone()

    assert workflow["current_stage"] == "script_draft"
    assert history["from_stage"] == "concept_draft"
    assert history["to_stage"] == "script_draft"
    assert history["event"] == "manual_brief_accepted"
    assert history["actor"] == actor
    assert history["to_lock_version"] == history["from_lock_version"] + 1
    assert version["snapshot"]["brief"] == brief
