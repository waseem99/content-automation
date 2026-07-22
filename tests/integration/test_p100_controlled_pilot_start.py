from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import (
    PilotCreateRequest,
    PilotItemRequest,
    ProductionMode,
)
from src.operations.settings import OperationsSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.test_p100_controlled_draft_bootstrap import (
    bootstrap_client,
    payload_for,
    seed_selectable_contents,
    state_counts,
)


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def controlled_start_client(database) -> TestClient:
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": "admin.one",
            "producer-key": "producer.one",
            "reviewer-key": "reviewer.one",
            "publisher-key": "publisher.bootstrap",
        },
        resolve_identities_from_database=True,
    )
    app = create_configured_app(
        database=database,
        auth_settings=auth,
        runtime_settings=OperatorRuntimeSettings(
            _env_file=None,
            database_require_schema=False,
        ),
        operations_settings=OperationsSettings(
            _env_file=None,
            environment="staging",
            release_key="p100-controlled-start-test",
            git_sha="1" * 40,
            image_digest="sha256:" + "2" * 64,
            configuration_digest="3" * 64,
            migration_head="0090_acceptance_start_actor.sql",
            requests_per_minute=1000,
            storage_capacity_bytes=1024 * 1024,
        ),
    )
    return TestClient(app)


def bootstrap_pilot(database, ready) -> dict:
    response = bootstrap_client(database).post(
        "/acceptance/pilots/bootstrap-draft",
        headers={"X-Operator-Key": "admin-key"},
        json=payload_for(ready),
    )
    assert response.status_code == 200, response.text
    return response.json()


def start_payload(bootstrap: dict) -> dict[str, str]:
    return {
        "bootstrap_request_sha256": bootstrap["bootstrap_request_sha256"],
        "runbook_sha256": bootstrap["runbook"]["sha256"],
    }


def test_controlled_start_revalidates_and_replays_without_side_effects(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    bootstrap = bootstrap_pilot(p89_database, ready)
    pilot_id = bootstrap["pilot"]["id"]
    client = controlled_start_client(p89_database)
    admin = {"X-Operator-Key": "admin-key"}

    paths = {route.path for route in client.app.routes}
    assert "/acceptance/pilots/{pilot_id}/start-readiness" in paths
    assert "/acceptance/pilots/{pilot_id}/start-controlled" in paths

    legacy = client.post(f"/acceptance/pilots/{pilot_id}/start", headers=admin)
    assert legacy.status_code == 422
    assert legacy.json()["detail"]["code"] == "pilot_controlled_start_required"

    denied = client.get(
        f"/acceptance/pilots/{pilot_id}/start-readiness",
        headers={"X-Operator-Key": "producer-key"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "acceptance_read_role_required"

    for key in ("reviewer-key", "publisher-key", "admin-key"):
        readiness = client.get(
            f"/acceptance/pilots/{pilot_id}/start-readiness",
            headers={"X-Operator-Key": key},
        )
        assert readiness.status_code == 200, readiness.text
        report = readiness.json()
        assert report["pilot_status"] == "draft"
        assert report["controlled_bootstrap"] is True
        assert report["scope"]["passed"] is True
        assert report["can_start"] is True
        assert report["blockers"] == []

    wrong_runbook = start_payload(bootstrap)
    wrong_runbook["runbook_sha256"] = "0" * 64
    denied_runbook = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=wrong_runbook,
    )
    assert denied_runbook.status_code == 422
    assert denied_runbook.json()["detail"]["code"] == "pilot_start_runbook_digest_mismatch"

    wrong_bootstrap = start_payload(bootstrap)
    wrong_bootstrap["bootstrap_request_sha256"] = "f" * 64
    denied_bootstrap = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=wrong_bootstrap,
    )
    assert denied_bootstrap.status_code == 422
    assert denied_bootstrap.json()["detail"]["code"] == "pilot_start_bootstrap_digest_mismatch"

    before = state_counts(p89_database)
    started = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=start_payload(bootstrap),
    )
    assert started.status_code == 200, started.text
    result = started.json()
    assert result["kind"] == "p100_controlled_start"
    assert result["reused"] is False
    assert result["pilot"]["status"] == "running"
    assert result["pilot"]["started_by"] == "admin.one"
    assert result["pilot"]["started_at"] is not None
    started_at = result["pilot"]["started_at"]

    after_start = state_counts(p89_database)
    assert after_start["events"] == before["events"] + 1
    for key in (
        "pilots",
        "pilot_items",
        "evidence",
        "generation_jobs",
        "reservations",
        "deliveries",
        "releases",
    ):
        assert after_start[key] == before[key]

    replay = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=start_payload(bootstrap),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["reused"] is True
    assert replay.json()["pilot"]["started_at"] == started_at
    assert replay.json()["pilot"]["started_by"] == "admin.one"
    assert state_counts(p89_database) == after_start

    post_readiness = client.get(
        f"/acceptance/pilots/{pilot_id}/start-readiness",
        headers=admin,
    )
    assert post_readiness.status_code == 200
    assert post_readiness.json()["pilot_status"] == "running"
    assert post_readiness.json()["can_start"] is False
    assert post_readiness.json()["start_event"]["start_mode"] == "controlled"

    with p89_database.connection() as conn:
        events = conn.execute(
            """SELECT actor,details FROM football_brief.acceptance_pilot_events
               WHERE pilot_id=%s AND event='pilot_started'""",
            (pilot_id,),
        ).fetchall()
    assert len(events) == 1
    assert events[0]["actor"] == "admin.one"
    assert events[0]["details"]["bootstrap_request_sha256"] == bootstrap[
        "bootstrap_request_sha256"
    ]


def test_controlled_start_blocks_stale_role_evidence_atomically(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    bootstrap = bootstrap_pilot(p89_database, ready)
    pilot_id = bootstrap["pilot"]["id"]
    client = controlled_start_client(p89_database)
    admin = {"X-Operator-Key": "admin-key"}

    with p89_database.transaction() as conn:
        conn.execute(
            "UPDATE football_brief.operator_users SET active=false "
            "WHERE operator_id='publisher.bootstrap'"
        )

    before = state_counts(p89_database)
    readiness = client.get(
        f"/acceptance/pilots/{pilot_id}/start-readiness",
        headers=admin,
    )
    assert readiness.status_code == 200
    assert readiness.json()["can_start"] is False
    assert any(
        blocker["code"] == "pilot_start_selection_evidence_incomplete"
        and "role_assignment" in blocker["missing_categories"]
        for blocker in readiness.json()["blockers"]
    )

    start = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=start_payload(bootstrap),
    )
    assert start.status_code == 422
    assert start.json()["detail"]["code"] == "pilot_not_ready_to_start"
    assert state_counts(p89_database) == before
    with p89_database.connection() as conn:
        pilot = conn.execute(
            "SELECT status,started_by,started_at FROM football_brief.acceptance_pilots WHERE id=%s",
            (pilot_id,),
        ).fetchone()
    assert pilot["status"] == "draft"
    assert pilot["started_by"] is None
    assert pilot["started_at"] is None


def test_controlled_start_blocks_duplicate_binding_and_legacy_start_records_actor(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    bootstrap = bootstrap_pilot(p89_database, ready)
    pilot_id = bootstrap["pilot"]["id"]
    selected = ready["contents"]["animal-x"][0]
    service = AcceptancePilotService(p89_database)
    other = service.create(
        PilotCreateRequest(
            pilot_key="p100-other-editable-pilot",
            acceptance_policy={"critical_defects_allowed": 0},
        ),
        actor="admin.one",
    )
    service.add_item(
        pilot_id=other["pilot"]["id"],
        request=PilotItemRequest(
            portfolio_content_id=selected["id"],
            content_version=int(selected["version"]),
            production_mode=ProductionMode.LOCAL_ONLY,
        ),
        actor="admin.one",
    )

    client = controlled_start_client(p89_database)
    admin = {"X-Operator-Key": "admin-key"}
    before = state_counts(p89_database)
    readiness = client.get(
        f"/acceptance/pilots/{pilot_id}/start-readiness",
        headers=admin,
    )
    assert readiness.status_code == 200
    assert readiness.json()["can_start"] is False
    assert any(
        blocker["code"] == "pilot_start_duplicate_binding"
        for blocker in readiness.json()["blockers"]
    )
    start = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers=admin,
        json=start_payload(bootstrap),
    )
    assert start.status_code == 422
    assert start.json()["detail"]["code"] == "pilot_not_ready_to_start"
    assert state_counts(p89_database) == before

    legacy = service.create(
        PilotCreateRequest(
            pilot_key="p100-legacy-start-preserved",
            acceptance_policy={},
        ),
        actor="admin.one",
    )
    legacy_id = legacy["pilot"]["id"]
    legacy_started = client.post(
        f"/acceptance/pilots/{legacy_id}/start",
        headers=admin,
    )
    assert legacy_started.status_code == 200, legacy_started.text
    assert legacy_started.json()["pilot"]["status"] == "running"
    assert legacy_started.json()["pilot"]["started_by"] == "admin.one"
    with p89_database.connection() as conn:
        event = conn.execute(
            """SELECT actor,details FROM football_brief.acceptance_pilot_events
               WHERE pilot_id=%s AND event='pilot_started'""",
            (legacy_id,),
        ).fetchone()
    assert event["actor"] == "admin.one"
    assert event["details"]["start_mode"] == "legacy"
