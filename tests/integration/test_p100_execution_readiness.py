from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import PilotCreateRequest, PilotItemRequest, ProductionMode
from src.application.acceptance.validated_service import (
    P100_RUNBOOK_RELATIVE_PATH,
    p100_runbook_sha256,
)
from src.operations.settings import OperationsSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.test_p100_acceptance_foundation import seed_pilot_contents


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def readiness_client(database) -> TestClient:
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": "admin.one",
            "producer-key": "producer.one",
            "reviewer-key": "reviewer.one",
            "publisher-key": "publisher.p100",
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
            release_key="p100-execution-readiness-test",
            git_sha="1" * 40,
            image_digest="sha256:" + "2" * 64,
            configuration_digest="3" * 64,
            migration_head="0089_acceptance_runbook_drill.sql",
            requests_per_minute=1000,
            storage_capacity_bytes=1024 * 1024,
        ),
    )
    return TestClient(app)


def create_bounded_pilot(database, seeded) -> tuple[object, dict[str, object]]:
    ready = seed_pilot_contents(database, seeded)
    service = AcceptancePilotService(database)
    pilot = service.create(
        PilotCreateRequest(
            pilot_key="p100-execution-readiness",
            acceptance_policy={"critical_defects_allowed": 0, "major_defects_allowed": 0},
        ),
        actor=str(seeded["admin"]),
    )["pilot"]
    for slug in ("animal-x", "rawr-nation"):
        for index, content in enumerate(ready["contents"][slug]):
            service.add_item(
                pilot_id=pilot["id"],
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
                actor=str(seeded["admin"]),
            )
    return pilot["id"], ready


def acceptance_row_counts(database, pilot_id) -> tuple[int, int]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT
                   (SELECT count(*) FROM football_brief.acceptance_pilot_evidence ape
                     JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
                    WHERE api.pilot_id=%s) AS evidence_count,
                   (SELECT count(*) FROM football_brief.acceptance_pilot_events
                    WHERE pilot_id=%s) AS event_count""",
            (pilot_id, pilot_id),
        ).fetchone()
    return int(row["evidence_count"]), int(row["event_count"])


def assign_reviewer_to_pilot_brands(database, brand_ids) -> None:
    with database.transaction() as conn:
        reviewer = conn.execute(
            "SELECT id FROM football_brief.operator_users WHERE operator_id='reviewer.one'"
        ).fetchone()
        for brand_id in brand_ids:
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,'admin.one') ON CONFLICT DO NOTHING""",
                (reviewer["id"], brand_id),
            )


def test_readiness_is_canonical_read_only_and_brand_scoped(
    p89_database,
    p89_seeded,
) -> None:
    pilot_id, ready = create_bounded_pilot(p89_database, p89_seeded)
    client = readiness_client(p89_database)
    path = f"/acceptance/pilots/{pilot_id}/readiness"

    registered_paths = {route.path for route in client.app.routes}
    assert "/acceptance/pilots/{pilot_id}/readiness" in registered_paths

    before = acceptance_row_counts(p89_database, pilot_id)

    producer = client.get(path, headers={"X-Operator-Key": "producer-key"})
    assert producer.status_code == 403
    assert producer.json()["detail"] == "acceptance_read_role_required"

    unassigned_reviewer = client.get(path, headers={"X-Operator-Key": "reviewer-key"})
    assert unassigned_reviewer.status_code == 403
    assert unassigned_reviewer.json()["detail"] == "pilot_brand_scope_required"

    admin = client.get(path, headers={"X-Operator-Key": "admin-key"})
    assert admin.status_code == 200, admin.text
    report = admin.json()
    assert report["scope"]["passed"] is True
    assert report["scope"]["item_count"] == 4
    assert report["scope"]["brand_counts"] == {"animal-x": 2, "rawr-nation": 2}
    assert report["scope"]["modes_by_brand"] == {
        "animal-x": ["local_only", "managed_render"],
        "rawr-nation": ["local_only", "managed_render"],
    }
    assert len(report["items"]) == 4
    assert report["ready_for_signoff"] is False
    assert report["ready_for_acceptance"] is False
    assert report["runbook"] == {
        "path": P100_RUNBOOK_RELATIVE_PATH,
        "sha256": p100_runbook_sha256(),
    }
    blocker_codes = {entry["code"] for entry in report["blockers"]}
    assert "pilot_not_running" in blocker_codes
    assert "pilot_item_canonical_evidence_incomplete" in blocker_codes
    assert "pilot_operations_evidence_missing" in blocker_codes
    assert "pilot_signoffs_incomplete" in blocker_codes
    assert "pilot_live_result_missing" in blocker_codes

    publisher = client.get(path, headers={"X-Operator-Key": "publisher-key"})
    assert publisher.status_code == 200, publisher.text

    assign_reviewer_to_pilot_brands(
        p89_database,
        (ready["brands"]["animal-x"], ready["brands"]["rawr-nation"]),
    )
    assigned_reviewer = client.get(path, headers={"X-Operator-Key": "reviewer-key"})
    assert assigned_reviewer.status_code == 200, assigned_reviewer.text

    after = acceptance_row_counts(p89_database, pilot_id)
    assert after == before
