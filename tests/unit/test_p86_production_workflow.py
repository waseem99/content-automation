from pathlib import Path

import pytest

from src.domain.production_workflow import (
    ProductionStage,
    ReviewDecision,
    WorkflowRuleError,
    WorkflowStatus,
    WorkflowVersionStatus,
    compatibility_stage,
    missing_requirements,
    reopen_plan,
    review_plan,
    submit_plan,
)


ROOT = Path(__file__).resolve().parents[2]


def test_work_submission_requires_exact_stage_evidence() -> None:
    with pytest.raises(WorkflowRuleError) as missing:
        submit_plan(
            stage=ProductionStage.SCRIPT_DRAFT,
            workflow_status=WorkflowStatus.ACTIVE,
            version_status=WorkflowVersionStatus.WORKING,
            snapshot={"script": {"text": "draft"}},
        )
    assert missing.value.code == "stage_prerequisites_missing"
    assert missing.value.details == {"missing": ["scene_plan"]}

    plan = submit_plan(
        stage=ProductionStage.SCRIPT_DRAFT,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.WORKING,
        snapshot={"script": {"text": "draft"}, "scene_plan": [{"scene": 1}]},
    )
    assert plan.to_stage == ProductionStage.SCRIPT_REVIEW
    assert plan.version_status == WorkflowVersionStatus.IN_REVIEW


def test_approval_seals_reviewed_version_and_creates_next_working_successor() -> None:
    plan = review_plan(
        stage=ProductionStage.SCRIPT_REVIEW,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.IN_REVIEW,
        decision=ReviewDecision.APPROVED,
        snapshot={"script": {"text": "approved"}, "scene_plan": [{"scene": 1}]},
        reviewer="reviewer.one",
        last_edited_by="producer.one",
    )
    assert plan.to_stage == ProductionStage.NARRATION_GENERATION
    assert plan.version_status == WorkflowVersionStatus.APPROVED
    assert plan.create_successor is True
    assert plan.complete_workflow is False


def test_publication_approval_completes_without_creating_an_editable_successor() -> None:
    plan = review_plan(
        stage=ProductionStage.PUBLICATION,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.IN_REVIEW,
        decision=ReviewDecision.APPROVED,
        snapshot={"delivery_result": {"platform_post_id": "post-1"}},
        reviewer="publisher.two",
        last_edited_by="publisher.one",
    )
    assert plan.to_stage == ProductionStage.PUBLISHED
    assert plan.workflow_status == WorkflowStatus.COMPLETED
    assert plan.version_status == WorkflowVersionStatus.APPROVED
    assert plan.create_successor is False
    assert plan.complete_workflow is True


def test_independent_review_is_required_for_the_exact_submitted_version() -> None:
    with pytest.raises(WorkflowRuleError) as denied:
        review_plan(
            stage=ProductionStage.CONCEPT_REVIEW,
            workflow_status=WorkflowStatus.ACTIVE,
            version_status=WorkflowVersionStatus.IN_REVIEW,
            decision=ReviewDecision.APPROVED,
            snapshot={"concept": "A complete concept"},
            reviewer="same.person",
            last_edited_by="same.person",
        )
    assert denied.value.code == "independent_review_required"


def test_changes_requested_returns_to_the_correct_editable_stage() -> None:
    plan = review_plan(
        stage=ProductionStage.LOCAL_PREVIEW_REVIEW,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.IN_REVIEW,
        decision=ReviewDecision.CHANGES_REQUESTED,
        snapshot={"preview_artifact_ids": ["asset-1"]},
        reviewer="reviewer.one",
        last_edited_by="producer.one",
    )
    assert plan.to_stage == ProductionStage.LOCAL_PREVIEW_GENERATION
    assert plan.version_status == WorkflowVersionStatus.CHANGES_REQUESTED
    assert plan.create_revision is True


def test_rejection_blocks_and_only_a_rejected_review_stage_can_reopen() -> None:
    rejected = review_plan(
        stage=ProductionStage.FINAL_REVIEW,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.IN_REVIEW,
        decision=ReviewDecision.REJECTED,
        snapshot={"final_video_artifact_id": "asset-1"},
        reviewer="reviewer.one",
        last_edited_by="producer.one",
    )
    assert rejected.workflow_status == WorkflowStatus.BLOCKED
    assert rejected.version_status == WorkflowVersionStatus.REJECTED

    reopened = reopen_plan(
        stage=rejected.to_stage,
        workflow_status=WorkflowStatus.BLOCKED,
        version_status=WorkflowVersionStatus.REJECTED,
    )
    assert reopened.to_stage == ProductionStage.FINAL_ASSEMBLY
    assert reopened.create_revision is True

    with pytest.raises(WorkflowRuleError) as invalid:
        reopen_plan(
            stage=ProductionStage.FINAL_REVIEW,
            workflow_status=WorkflowStatus.ACTIVE,
            version_status=WorkflowVersionStatus.REJECTED,
        )
    assert invalid.value.code == "workflow_not_blocked"


def test_stage_requirements_and_compatibility_projection_are_explicit() -> None:
    assert missing_requirements(ProductionStage.SPEND_APPROVAL, {"spend_estimate": 4.5}) == ["spend_ceiling"]
    assert compatibility_stage(ProductionStage.STORYBOARD_REVIEW, WorkflowStatus.ACTIVE) == "preview"
    assert compatibility_stage(ProductionStage.PACKAGE_APPROVAL, WorkflowStatus.ACTIVE) == "package"
    assert compatibility_stage(ProductionStage.PUBLICATION, WorkflowStatus.ACTIVE) == "ready"
    assert compatibility_stage(ProductionStage.FINAL_REVIEW, WorkflowStatus.BLOCKED) == "blocked"


def test_migration_and_service_preserve_exact_review_evidence() -> None:
    migration = (ROOT / "migrations" / "0031_versioned_production_workflow.sql").read_text(encoding="utf-8")
    domain = (ROOT / "src" / "domain" / "production_workflow.py").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "production_workflow_service.py").read_text(encoding="utf-8")

    assert "CREATE TABLE football_brief.production_workflows" in migration
    assert "CREATE TABLE football_brief.production_workflow_versions" in migration
    assert "CREATE TABLE football_brief.production_workflow_stage_history" in migration
    assert "CREATE TABLE football_brief.production_workflow_assignments" in migration
    assert "CREATE TABLE football_brief.production_workflow_comments" in migration
    assert "CREATE TABLE football_brief.production_workflow_decisions" in migration
    assert "DEFERRABLE INITIALLY DEFERRED" in migration
    assert "Production workflow history and decisions are immutable" in migration
    assert "Submitted workflow versions are immutable" in migration
    assert "Workflow updates must increment lock_version by exactly one" in migration
    assert "create_successor" in domain
    assert "independent_review_required" in domain
    assert "workflow_conflict" in service
    assert "increment_content_version=True" in service
    assert migration.rstrip().endswith("COMMIT;")
