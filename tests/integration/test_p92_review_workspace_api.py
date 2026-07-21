from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready


pytestmark = pytest.mark.integration


def review_client(database, ready) -> TestClient:
    brand_one = str(ready["brand_one"])
    brand_two = str(ready["brand_two"])
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["outsider"]: OperatorIdentity(
            operator_id=str(ready["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_two}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(ready["admin"]),
            "producer-key": str(ready["producer"]),
            "reviewer-key": str(ready["reviewer"]),
            "outsider-key": str(ready["outsider"]),
        },
        identities=identities,
    )
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=runtime,
        )
    )


def test_review_workspace_api_enforces_brand_roles_and_assignee_progress(
    p89_database, p91_ready
) -> None:
    client = review_client(p89_database, p91_ready)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    content_id = p91_ready["content_one"]
    script_version_id = p91_ready["script_version_id"]

    assert client.get(f"/review/content/{content_id}", headers=reviewer).status_code == 200
    assert client.get(f"/review/content/{content_id}", headers=admin).status_code == 200
    assert client.get(f"/review/content/{content_id}", headers=outsider).status_code == 403

    compared = client.post(
        "/review/compare",
        headers=reviewer,
        json={"target_type": "script_version", "current_id": str(script_version_id)},
    )
    assert compared.status_code == 200, compared.text
    assert compared.json()["current"]["id"] == str(script_version_id)
    assert "_parent_id" not in compared.json()["current"]

    outsider_compare = client.post(
        "/review/compare",
        headers=outsider,
        json={"target_type": "script_version", "current_id": str(script_version_id)},
    )
    assert outsider_compare.status_code == 403

    producer_comment = client.post(
        "/review/comments",
        headers=producer,
        json={
            "target_type": "script_version",
            "target_id": str(script_version_id),
            "comment_type": "general",
            "body": "Producer note recorded against this exact script version.",
        },
    )
    assert producer_comment.status_code == 200, producer_comment.text
    assert producer_comment.json()["revision_task"] is None

    producer_change_request = client.post(
        "/review/comments",
        headers=producer,
        json={
            "target_type": "script_version",
            "target_id": str(script_version_id),
            "comment_type": "change_request",
            "body": "A producer cannot create their own blocking task.",
            "blocking": True,
            "revision_task": {
                "task_type": "script_edit",
                "title": "Producer self-task denied",
                "instructions": "This request must not be accepted.",
                "assignee_operator_id": p91_ready["producer"],
            },
        },
    )
    assert producer_change_request.status_code == 403

    reviewer_change_request = client.post(
        "/review/comments",
        headers=reviewer,
        json={
            "target_type": "script_version",
            "target_id": str(script_version_id),
            "comment_type": "change_request",
            "body": "Tighten the hook while preserving the exact factual support.",
            "blocking": True,
            "revision_task": {
                "task_type": "script_edit",
                "title": "Tighten script hook",
                "instructions": "Create a child script version and preserve the source pack.",
                "assignee_operator_id": p91_ready["producer"],
                "priority": "high",
                "blocker": True,
            },
        },
    )
    assert reviewer_change_request.status_code == 200, reviewer_change_request.text
    task = reviewer_change_request.json()["revision_task"]

    reviewer_inbox = client.get(
        "/review/inbox?item_type=revision_task&blocker=true",
        headers=reviewer,
    )
    assert reviewer_inbox.status_code == 200
    assert any(item["inbox_item_id"] == task["id"] for item in reviewer_inbox.json()["items"])

    outsider_inbox = client.get(
        "/review/inbox?item_type=revision_task&blocker=true",
        headers=outsider,
    )
    assert outsider_inbox.status_code == 200
    assert not any(item["inbox_item_id"] == task["id"] for item in outsider_inbox.json()["items"])

    outsider_start = client.post(
        f"/review/tasks/{task['id']}",
        headers=outsider,
        json={"expected_lock_version": 1, "status": "in_progress"},
    )
    assert outsider_start.status_code == 403

    producer_reassign = client.post(
        f"/review/tasks/{task['id']}",
        headers=producer,
        json={
            "expected_lock_version": 1,
            "assignee_operator_id": p91_ready["reviewer"],
        },
    )
    assert producer_reassign.status_code == 403

    producer_start = client.post(
        f"/review/tasks/{task['id']}",
        headers=producer,
        json={"expected_lock_version": 1, "status": "in_progress"},
    )
    assert producer_start.status_code == 200, producer_start.text
    assert producer_start.json()["task"]["status"] == "in_progress"

    reviewer_priority = client.post(
        f"/review/tasks/{task['id']}",
        headers=reviewer,
        json={"expected_lock_version": 2, "priority": "urgent"},
    )
    assert reviewer_priority.status_code == 200, reviewer_priority.text
    assert reviewer_priority.json()["task"]["priority"] == "urgent"
