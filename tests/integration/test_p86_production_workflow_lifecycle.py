from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from src.application.production_workflow_service import (
    ProductionWorkflowError,
    ProductionWorkflowService,
)
from src.domain.production_workflow import ProductionStage, ReviewDecision
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


@pytest.fixture()
def database() -> Database:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=3,
    )
    db = Database(settings)
    db.open(require_schema=False)
    with db.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(db, settings.migrations_dir)
    try:
        yield db
    finally:
        with db.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        db.close()


@pytest.fixture()
def seeded(database: Database) -> dict[str, object]:
    operators = {
        "admin": ("admin.one", "Admin One", "admin"),
        "producer": ("producer.one", "Producer One", "producer"),
        "reviewer": ("reviewer.one", "Reviewer One", "reviewer"),
        "publisher": ("publisher.one", "Publisher One", "publisher"),
        "outsider": ("producer.outside", "Outside Producer", "producer"),
    }
    with database.transaction() as conn:
        operator_rows = {}
        for key, (operator_id, display_name, role) in operators.items():
            user = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id, display_name, created_by)
                   VALUES (%s,%s,'bootstrap') RETURNING id""",
                (operator_id, display_name),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id, role, assigned_by)
                   VALUES (%s,%s,'bootstrap')""",
                (user["id"], role),
            )
            operator_rows[key] = user["id"]

        brand = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode, monthly_target)
               VALUES ('workflow-brand','Workflow Brand','Educational video','facebook','video',24)
               RETURNING id"""
        ).fetchone()
        for key in ("producer", "reviewer", "publisher"):
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id, brand_id, assigned_by)
                   VALUES (%s,%s,'admin.one')""",
                (operator_rows[key], brand["id"]),
            )

        voice = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms, approved_by, approved_at)
               VALUES ('kokoro-onnx','af_heart','Workflow Voice','premade','approved',
                       ARRAY['en'], ARRAY['facebook'], 'admin.one', now())
               RETURNING id"""
        ).fetchone()
        profile = conn.execute(
            """INSERT INTO football_brief.brand_profiles
               (brand_id, version, default_language, tone, platforms, created_by)
               VALUES (%s,1,'en-US','clear factual narration',ARRAY['facebook'],'admin.one')
               RETURNING id""",
            (brand["id"],),
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.brand_narration_presets
               (brand_profile_id, preset_key, display_name, role, approved_voice_id,
                language, is_default)
               VALUES (%s,'primary','Primary','primary',%s,'en-US',true)""",
            (profile["id"], voice["id"]),
        )
        conn.execute(
            """UPDATE football_brief.brand_profiles
               SET status='active', activated_by='admin.one', activated_at=now()
               WHERE id=%s""",
            (profile["id"],),
        )

        plan = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id, month_start, target_count, created_by)
               VALUES (%s, DATE '2026-08-01', 24, 'admin.one') RETURNING id""",
            (brand["id"],),
        ).fetchone()
        content = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id, scheduled_for, title, concept, format, concept_fingerprint, semantic_key)
               VALUES (%s, DATE '2026-08-02', 'Octopus sensing',
                       'Explain how an octopus arm senses its environment.', 'vertical_short',
                       %s, 'octopus-sensing') RETURNING id""",
            (plan["id"], "c" * 64),
        ).fetchone()
    return {
        "brand_id": brand["id"],
        "content_id": content["id"],
        "profile_id": profile["id"],
        **{key: value[0] for key, value in operators.items()},
    }


def test_approval_seals_version_and_changes_request_creates_new_content_revision(
    database: Database, seeded: dict[str, object]
) -> None:
    service = ProductionWorkflowService(database)
    created = service.initialize(content_id=seeded["content_id"], actor=seeded["producer"])
    workflow_id = created["workflow_id"]

    submitted = service.submit(
        workflow_id=workflow_id,
        expected_lock_version=1,
        actor=seeded["producer"],
    )
    assert submitted["workflow"]["current_stage"] == ProductionStage.CONCEPT_REVIEW.value
    assert submitted["workflow"]["version_status"] == "in_review"
    assert submitted["workflow"]["lock_version"] == 2

    with pytest.raises(ProductionWorkflowError) as self_review:
        service.decide(
            workflow_id=workflow_id,
            expected_lock_version=2,
            reviewer=seeded["producer"],
            decision=ReviewDecision.APPROVED,
            rationale="I approve my own concept",
        )
    assert self_review.value.code == "independent_review_required"

    approved = service.decide(
        workflow_id=workflow_id,
        expected_lock_version=2,
        reviewer=seeded["reviewer"],
        decision=ReviewDecision.APPROVED,
        rationale="Concept is clear and sufficiently original",
    )
    assert approved["workflow"]["current_stage"] == ProductionStage.SCRIPT_DRAFT.value
    assert approved["workflow"]["workflow_version"] == 2
    assert approved["workflow"]["version_status"] == "working"
    assert approved["workflow"]["lock_version"] == 3
    assert [row["status"] for row in approved["versions"]] == ["working", "approved"]
    assert approved["decisions"][0]["workflow_version_id"] == approved["versions"][1]["id"]

    edited = service.update_snapshot(
        workflow_id=workflow_id,
        expected_lock_version=3,
        actor=seeded["producer"],
        patch={
            "script": {"narration": "An octopus arm samples touch and chemicals."},
            "scene_plan": [{"scene": 1, "purpose": "hook"}],
        },
    )
    assert edited["workflow"]["lock_version"] == 4
    submitted_script = service.submit(
        workflow_id=workflow_id,
        expected_lock_version=4,
        actor=seeded["producer"],
        rationale="Script and scene plan ready",
    )
    assert submitted_script["workflow"]["current_stage"] == ProductionStage.SCRIPT_REVIEW.value

    reviewed_version_id = submitted_script["workflow"]["current_version_id"]
    changes = service.decide(
        workflow_id=workflow_id,
        expected_lock_version=5,
        reviewer=seeded["reviewer"],
        decision=ReviewDecision.CHANGES_REQUESTED,
        rationale="Shorten the hook and clarify the chemical sensing claim",
    )
    assert changes["workflow"]["current_stage"] == ProductionStage.SCRIPT_DRAFT.value
    assert changes["workflow"]["workflow_version"] == 3
    assert changes["workflow"]["content_version"] == 2
    assert changes["workflow"]["lock_version"] == 6
    assert changes["versions"][1]["id"] == reviewed_version_id
    assert changes["versions"][1]["status"] == "changes_requested"

    with pytest.raises(Exception, match="immutable"):
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.production_workflow_versions
                   SET snapshot='{}'::jsonb WHERE id=%s""",
                (reviewed_version_id,),
            )

    with pytest.raises(ProductionWorkflowError) as stale:
        service.update_snapshot(
            workflow_id=workflow_id,
            expected_lock_version=5,
            actor=seeded["producer"],
            patch={"script": {"narration": "stale edit"}},
        )
    assert stale.value.code == "workflow_conflict"
    assert stale.value.details == {"expected": 5, "actual": 6}


def test_rejection_blocks_reopen_creates_revision_and_assignment_queue_is_scoped(
    database: Database, seeded: dict[str, object]
) -> None:
    service = ProductionWorkflowService(database)
    workflow_id = service.initialize(
        content_id=seeded["content_id"], actor=seeded["producer"]
    )["workflow_id"]
    service.submit(
        workflow_id=workflow_id,
        expected_lock_version=1,
        actor=seeded["producer"],
    )
    rejected = service.decide(
        workflow_id=workflow_id,
        expected_lock_version=2,
        reviewer=seeded["reviewer"],
        decision=ReviewDecision.REJECTED,
        rationale="Concept conflicts with the brand restrictions",
    )
    assert rejected["workflow"]["status"] == "blocked"
    assert rejected["workflow"]["compatibility_stage"] == "blocked"
    assert rejected["workflow"]["version_status"] == "rejected"

    with pytest.raises(ProductionWorkflowError) as blocked:
        service.submit(
            workflow_id=workflow_id,
            expected_lock_version=3,
            actor=seeded["producer"],
        )
    assert blocked.value.code == "workflow_not_active"

    reopened = service.reopen(
        workflow_id=workflow_id,
        expected_lock_version=3,
        actor=seeded["admin"],
        rationale="Editorial lead approved a bounded rewrite",
    )
    assert reopened["workflow"]["status"] == "active"
    assert reopened["workflow"]["current_stage"] == ProductionStage.CONCEPT_DRAFT.value
    assert reopened["workflow"]["workflow_version"] == 2
    assert reopened["workflow"]["content_version"] == 2
    assert reopened["workflow"]["lock_version"] == 4

    with pytest.raises(ProductionWorkflowError) as wrong_role:
        service.assign(
            workflow_id=workflow_id,
            expected_lock_version=4,
            assignee=seeded["reviewer"],
            actor=seeded["admin"],
        )
    assert wrong_role.value.code == "assignee_role_mismatch"

    with pytest.raises(ProductionWorkflowError) as wrong_brand:
        service.assign(
            workflow_id=workflow_id,
            expected_lock_version=4,
            assignee=seeded["outsider"],
            actor=seeded["admin"],
        )
    assert wrong_brand.value.code == "assignee_brand_access_denied"

    due_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assigned = service.assign(
        workflow_id=workflow_id,
        expected_lock_version=4,
        assignee=seeded["producer"],
        actor=seeded["admin"],
        due_at=due_at,
    )
    assert assigned["assignment"]["assignee_operator_id"] == seeded["producer"]
    assert assigned["workflow"]["lock_version"] == 5

    overdue = service.queue(
        brand_ids=[seeded["brand_id"]],
        assignee=seeded["producer"],
        overdue=True,
    )
    assert len(overdue) == 1
    assert overdue[0]["id"] == workflow_id
    assert overdue[0]["overdue"] is True
    assert service.queue(brand_ids=[], overdue=True) == []


def test_comments_are_version_bound_append_only_and_resolve_once(
    database: Database, seeded: dict[str, object]
) -> None:
    service = ProductionWorkflowService(database)
    workflow_id = service.initialize(
        content_id=seeded["content_id"], actor=seeded["producer"]
    )["workflow_id"]
    detail = service.detail(workflow_id=workflow_id)
    version_id = detail["workflow"]["current_version_id"]
    comment = service.add_comment(
        workflow_id=workflow_id,
        workflow_version_id=version_id,
        stage=ProductionStage.CONCEPT_DRAFT,
        actor=seeded["reviewer"],
        comment_type="factual",
        body="Cite the sensory receptor evidence before review.",
    )["comment"]
    resolved = service.resolve_comment(comment_id=comment["id"], actor=seeded["producer"])
    assert resolved["comment"]["resolved_by_operator_id"] == seeded["producer"]
    assert resolved["comment"]["resolved_at"] is not None

    with pytest.raises(ProductionWorkflowError) as twice:
        service.resolve_comment(comment_id=comment["id"], actor=seeded["producer"])
    assert twice.value.code == "comment_not_found_or_already_resolved"

    with pytest.raises(Exception, match="append-only"):
        with database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.production_workflow_comments SET body='rewritten' WHERE id=%s",
                (comment["id"],),
            )
