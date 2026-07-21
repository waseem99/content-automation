from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from src.application.audio.models import AlignmentSource
from src.application.review_workspace.models import (
    CommentType,
    CompareTarget,
    InboxFilters,
    ReviewCommentRequest,
    ReviewTarget,
    RevisionTaskRequest,
    RevisionTaskStatus,
    TaskMutationRequest,
    TaskType,
)
from src.application.review_workspace.service import ReviewWorkspaceService
from src.application.visuals.models import (
    ShotDecision,
    ShotDecisionRequest,
    ShotRevisionRequest,
)
from src.application.visuals.review_service import VisualReviewService
from src.application.visuals.validated_service import ValidatedVisualProjectService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p90_audio_support import p90_ready
from tests.integration.p91_visual_support import p91_ready, project_request
from tests.integration.test_p90_audio_lifecycle import (
    initialize_and_select_takes,
    register_clean_mix,
)


pytestmark = pytest.mark.integration


def test_change_request_creates_scoped_task_and_completion_resolves_comment(
    p89_database, p91_ready
) -> None:
    service = ReviewWorkspaceService(p89_database)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    created = service.create_comment(
        request=ReviewCommentRequest(
            target_type=ReviewTarget.SCRIPT_VERSION,
            target_id=p91_ready["script_version_id"],
            comment_type=CommentType.CHANGE_REQUEST,
            body="Narrow the hook wording and keep the exact approved factual support.",
            blocking=True,
            revision_task=RevisionTaskRequest(
                task_type=TaskType.SCRIPT_EDIT,
                title="Revise hook wording",
                instructions="Create a child script version; do not rewrite the approved source pack.",
                assignee_operator_id=p91_ready["producer"],
                due_at=due,
                priority="high",
                blocker=True,
            ),
        ),
        actor=p91_ready["reviewer"],
    )
    comment_id = created["comment"]["id"]
    task_id = created["revision_task"]["id"]
    assert created["revision_task"]["target_script_version_id"] == p91_ready["script_version_id"]
    assert created["revision_task"]["lock_version"] == 1

    own_inbox = service.inbox(
        filters=InboxFilters(blocker=True, item_types=("revision_task",)),
        allowed_brand_ids=[p91_ready["brand_one"]],
    )
    assert any(str(item["inbox_item_id"]) == str(task_id) for item in own_inbox)
    other_brand = service.inbox(
        filters=InboxFilters(blocker=True),
        allowed_brand_ids=[p91_ready["brand_two"]],
    )
    assert not any(str(item["inbox_item_id"]) == str(task_id) for item in other_brand)

    with pytest.raises(psycopg.Error, match="task completion"):
        service.resolve_comment(comment_id=comment_id, actor=p91_ready["reviewer"])

    started = service.mutate_task(
        task_id=task_id,
        request=TaskMutationRequest(
            expected_lock_version=1,
            status=RevisionTaskStatus.IN_PROGRESS,
        ),
        actor=p91_ready["producer"],
    )
    assert started["task"]["lock_version"] == 2
    assert started["events"][-1]["event"] == "started"

    completed = service.mutate_task(
        task_id=task_id,
        request=TaskMutationRequest(
            expected_lock_version=2,
            status=RevisionTaskStatus.COMPLETED,
        ),
        actor=p91_ready["producer"],
    )
    assert completed["task"]["status"] == "completed"
    assert completed["events"][-1]["event"] == "completed"
    workspace = service.workspace(content_id=p91_ready["content_one"])
    comment = next(item for item in workspace["comments"] if str(item["id"]) == str(comment_id))
    assert comment["resolved_at"] is not None

    with p89_database.connection() as conn:
        workflow = conn.execute(
            "SELECT * FROM football_brief.production_workflows WHERE portfolio_content_id=%s",
            (p91_ready["content_one"],),
        ).fetchone()
    with pytest.raises(psycopg.Error, match="must create one revision task"):
        with p89_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.creator_review_comments
                   (portfolio_content_id,production_workflow_id,workflow_version_id,stage,
                    target_type,target_script_version_id,comment_type,body,blocking,
                    author_operator_id)
                   VALUES (%s,%s,%s,%s,'script_version',%s,'change_request',
                           'Orphan request must fail at commit.',true,%s)""",
                (
                    p91_ready["content_one"],workflow["id"],workflow["current_version_id"],
                    workflow["current_stage"],p91_ready["script_version_id"],
                    p91_ready["reviewer"],
                ),
            )


def test_timed_audio_comment_is_bounded_by_exact_mix(p89_database, p90_ready) -> None:
    audio_service, detail = initialize_and_select_takes(
        p89_database,p90_ready,timing_source=AlignmentSource.FORCED_ALIGNMENT
    )
    mixed = register_clean_mix(
        p89_database,p90_ready,audio_service,detail,
        alignment_source=AlignmentSource.FORCED_ALIGNMENT,
    )
    mix_id = mixed["production"]["current_mix_version_id"]
    service = ReviewWorkspaceService(p89_database)
    created = service.create_comment(
        request=ReviewCommentRequest(
            target_type=ReviewTarget.AUDIO_MIX_VERSION,
            target_id=mix_id,
            comment_type=CommentType.TIMING,
            body="Reduce the pause in this exact two-second interval.",
            timeline_start_ms=1000,
            timeline_end_ms=3000,
        ),
        actor=p90_ready["reviewer"],
    )
    assert created["comment"]["timeline_start_ms"] == 1000
    assert created["comment"]["target_audio_mix_version_id"] == mix_id

    with pytest.raises(psycopg.Error, match="exceeds the exact audio mix duration"):
        service.create_comment(
            request=ReviewCommentRequest(
                target_type=ReviewTarget.AUDIO_MIX_VERSION,
                target_id=mix_id,
                comment_type=CommentType.TIMING,
                body="This interval extends beyond the mix and must fail.",
                timeline_start_ms=59000,
                timeline_end_ms=61000,
            ),
            actor=p90_ready["reviewer"],
        )
    compared = service.compare(
        request=CompareTarget(target_type=ReviewTarget.AUDIO_MIX_VERSION,current_id=mix_id)
    )
    assert compared["current"]["id"] == mix_id
    assert compared["previous"] is None


def test_visual_child_version_compares_against_exact_parent(p89_database, p91_ready) -> None:
    visuals = ValidatedVisualProjectService(p89_database)
    review = VisualReviewService(p89_database)
    initialized = visuals.initialize(
        content_id=p91_ready["content_one"],
        request=project_request(p91_ready,base_seed=950000),
        actor=p91_ready["producer"],
    )
    shot = initialized["shots"][0]
    changed = review.decide_shot(
        project_id=initialized["project"]["id"],
        shot_id=shot["id"],
        shot_version_id=shot["current_version_id"],
        request=ShotDecisionRequest(
            expected_shot_lock_version=shot["lock_version"],
            decision=ShotDecision.CHANGES_REQUESTED,
            rationale="Move the landmark to the right third and soften the top light.",
        ),
        reviewer=p91_ready["reviewer"],
    )
    changed_shot = next(item for item in changed["shots"] if str(item["id"]) == str(shot["id"]))
    revised = visuals.revise_shot(
        project_id=initialized["project"]["id"],
        shot_id=shot["id"],
        request=ShotRevisionRequest(
            expected_shot_lock_version=changed_shot["lock_version"],
            reason="Apply the exact review direction.",
            prompt_patch={"environment":{"landmark":"fan coral on right third"}},
            negative_prompt_append="moved landmark",
            base_seed=960000,
        ),
        actor=p91_ready["producer"],
    )
    revised_shot = next(item for item in revised["shots"] if str(item["id"]) == str(shot["id"]))
    compared = ReviewWorkspaceService(p89_database).compare(
        request=CompareTarget(
            target_type=ReviewTarget.VISUAL_SHOT_VERSION,
            current_id=revised_shot["current_version_id"],
        )
    )
    assert compared["current"]["version"] == 2
    assert compared["previous"]["id"] == shot["current_version_id"]
    assert any(item["field"] == "compiled_prompt" for item in compared["differences"])
