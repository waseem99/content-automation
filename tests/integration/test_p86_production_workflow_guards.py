from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app


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
        "producer_one": ("producer.one", "Producer One", "producer"),
        "producer_two": ("producer.two", "Producer Two", "producer"),
        "reviewer": ("reviewer.one", "Reviewer One", "reviewer"),
    }
    with database.transaction() as conn:
        user_ids = {}
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
            user_ids[key] = user["id"]

        brand = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode, monthly_target)
               VALUES ('workflow-guard-brand','Workflow Guard Brand','Education','facebook','video',24)
               RETURNING id"""
        ).fetchone()
        for key in ("producer_one", "producer_two", "reviewer"):
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id, brand_id, assigned_by)
                   VALUES (%s,%s,'admin.one')""",
                (user_ids[key], brand["id"]),
            )

        voice = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms, approved_by, approved_at)
               VALUES ('kokoro-onnx','guard_voice','Guard Voice','premade','approved',
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
        content_ids = []
        for index in (1, 2):
            content = conn.execute(
                """INSERT INTO football_brief.portfolio_content
                   (plan_id, scheduled_for, title, concept, format, concept_fingerprint, semantic_key)
                   VALUES (%s, DATE '2026-08-02', %s, %s, 'vertical_short', %s, %s)
                   RETURNING id""",
                (
                    plan["id"],
                    f"Workflow guard {index}",
                    f"Complete concept {index}",
                    str(index) * 64,
                    f"workflow-guard-{index}",
                ),
            ).fetchone()
            content_ids.append(content["id"])

    return {
        "brand_id": brand["id"],
        "content_one": content_ids[0],
        "content_two": content_ids[1],
        **{key: value[0] for key, value in operators.items()},
    }


def client_for(database: Database, seeded: dict[str, object]) -> TestClient:
    brand_id = str(seeded["brand_id"])
    identities = {
        seeded["admin"]: OperatorIdentity(
            operator_id=str(seeded["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        seeded["producer_one"]: OperatorIdentity(
            operator_id=str(seeded["producer_one"]),
            key_name="producer-one-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
        seeded["producer_two"]: OperatorIdentity(
            operator_id=str(seeded["producer_two"]),
            key_name="producer-two-key",
            display_name="Producer Two",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
        seeded["reviewer"]: OperatorIdentity(
            operator_id=str(seeded["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(seeded["admin"]),
            "producer-one-key": str(seeded["producer_one"]),
            "producer-two-key": str(seeded["producer_two"]),
            "reviewer-key": str(seeded["reviewer"]),
        },
        identities=identities,
    )
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    return TestClient(create_configured_app(database=database, auth_settings=auth, runtime_settings=runtime))


def test_active_assignment_and_comment_workflow_ownership_are_enforced(
    database: Database, seeded: dict[str, object]
) -> None:
    client = client_for(database, seeded)
    producer_one = {"X-Operator-Key": "producer-one-key"}
    producer_two = {"X-Operator-Key": "producer-two-key"}
    admin = {"X-Operator-Key": "admin-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}

    first = client.post(
        f"/production/content/{seeded['content_one']}/workflow",
        headers=producer_one,
    )
    assert first.status_code == 200, first.text
    first_payload = first.json()
    first_workflow_id = first_payload["workflow"]["id"]
    first_version_id = first_payload["workflow"]["current_version_id"]

    assigned = client.post(
        f"/production/workflows/{first_workflow_id}/assignments",
        headers=admin,
        json={
            "expected_lock_version": 1,
            "assignee_operator_id": seeded["producer_one"],
        },
    )
    assert assigned.status_code == 200, assigned.text

    denied = client.post(
        f"/production/workflows/{first_workflow_id}/snapshot",
        headers=producer_two,
        json={"expected_lock_version": 2, "patch": {"concept": "Unauthorized rewrite"}},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "workflow_assigned_to_another_operator"

    allowed = client.post(
        f"/production/workflows/{first_workflow_id}/snapshot",
        headers=producer_one,
        json={"expected_lock_version": 2, "patch": {"concept": "Assigned producer edit"}},
    )
    assert allowed.status_code == 200, allowed.text

    comment = client.post(
        f"/production/workflows/{first_workflow_id}/comments",
        headers=reviewer,
        json={
            "workflow_version_id": first_version_id,
            "stage": "concept_draft",
            "comment_type": "factual",
            "body": "Verify the factual framing.",
        },
    )
    assert comment.status_code == 200, comment.text
    comment_id = comment.json()["comment"]["id"]

    second = client.post(
        f"/production/content/{seeded['content_two']}/workflow",
        headers=producer_one,
    )
    assert second.status_code == 200, second.text
    second_workflow_id = second.json()["workflow"]["id"]

    wrong_workflow = client.post(
        f"/production/workflows/{second_workflow_id}/comments/{comment_id}/resolve",
        headers=reviewer,
    )
    assert wrong_workflow.status_code == 404
    assert wrong_workflow.json()["detail"] == "comment_not_found"


def test_terminal_versions_and_evidence_records_fail_closed(
    database: Database, seeded: dict[str, object]
) -> None:
    client = client_for(database, seeded)
    producer = {"X-Operator-Key": "producer-one-key"}
    admin = {"X-Operator-Key": "admin-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}

    created = client.post(
        f"/production/content/{seeded['content_one']}/workflow",
        headers=producer,
    ).json()
    workflow_id = created["workflow"]["id"]
    version_id = created["workflow"]["current_version_id"]

    assignment = client.post(
        f"/production/workflows/{workflow_id}/assignments",
        headers=admin,
        json={
            "expected_lock_version": 1,
            "assignee_operator_id": seeded["producer_one"],
        },
    ).json()["assignment"]

    submitted = client.post(
        f"/production/workflows/{workflow_id}/submit",
        headers=producer,
        json={"expected_lock_version": 2, "rationale": "Concept ready"},
    )
    assert submitted.status_code == 200, submitted.text

    approved = client.post(
        f"/production/workflows/{workflow_id}/decisions",
        headers=reviewer,
        json={
            "expected_lock_version": 3,
            "decision": "approved",
            "rationale": "Independent concept approval",
        },
    )
    assert approved.status_code == 200, approved.text

    with pytest.raises(Exception, match="Invalid production workflow version status transition"):
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.production_workflow_versions
                   SET status='working', decided_at=NULL WHERE id=%s""",
                (UUID(version_id),),
            )

    with pytest.raises(Exception, match="cannot be deleted"):
        with database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.production_workflow_assignments WHERE id=%s",
                (UUID(assignment["id"]),),
            )

    current = approved.json()["workflow"]
    comment = client.post(
        f"/production/workflows/{workflow_id}/comments",
        headers=reviewer,
        json={
            "workflow_version_id": current["current_version_id"],
            "stage": current["current_stage"],
            "comment_type": "general",
            "body": "Carry the approved framing into the next stage.",
        },
    ).json()["comment"]

    with pytest.raises(Exception, match="resolved_comment_is_consistent"):
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.production_workflow_comments
                   SET resolved_by_operator_id=%s WHERE id=%s""",
                (seeded["producer_one"], UUID(comment["id"])),
            )

    with pytest.raises(Exception, match="cannot be deleted"):
        with database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.production_workflow_comments WHERE id=%s",
                (UUID(comment["id"]),),
            )
