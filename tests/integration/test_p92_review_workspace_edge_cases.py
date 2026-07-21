from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.review_workspace.models import CompareTarget, ReviewTarget
from src.application.review_workspace.service import ReviewWorkspaceError
from src.application.review_workspace.validated_service import ValidatedReviewWorkspaceService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.test_p92_review_workspace_api import review_client


pytestmark = pytest.mark.integration


def test_comparison_rejects_another_content_lineage(p89_database, p91_ready) -> None:
    with p89_database.connection() as conn:
        first = conn.execute(
            "SELECT current_version_id FROM football_brief.production_workflows WHERE id=%s",
            (p91_ready["workflow_one"],),
        ).fetchone()
        second = conn.execute(
            "SELECT current_version_id FROM football_brief.production_workflows WHERE id=%s",
            (p91_ready["workflow_two"],),
        ).fetchone()
    with pytest.raises(ReviewWorkspaceError, match="comparison_target_content_mismatch"):
        ValidatedReviewWorkspaceService(p89_database).compare(
            request=CompareTarget(
                target_type=ReviewTarget.WORKFLOW_VERSION,
                current_id=first["current_version_id"],
                previous_id=second["current_version_id"],
            )
        )


def test_api_missing_target_is_404_and_workspace_has_canonical_history(
    p89_database, p91_ready
) -> None:
    client = review_client(p89_database, p91_ready)
    admin = {"X-Operator-Key": "admin-key"}
    missing = client.post(
        "/review/compare",
        headers=admin,
        json={"target_type": "script_version", "current_id": str(uuid4())},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "review_target_not_found"

    workspace = client.get(
        f"/review/content/{p91_ready['content_one']}",
        headers=admin,
    )
    assert workspace.status_code == 200, workspace.text
    body = workspace.json()
    assert set(body["decision_history"]) == {
        "workflow",
        "script",
        "audio",
        "visual_project",
        "visual_candidate",
    }
    assert isinstance(body["render_jobs"], list)
