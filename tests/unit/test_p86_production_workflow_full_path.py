from src.domain.production_workflow import (
    ProductionStage,
    ReviewDecision,
    WorkflowStatus,
    WorkflowVersionStatus,
    review_plan,
    submit_plan,
)


def test_complete_production_path_has_no_unreachable_stage() -> None:
    snapshot = {
        "concept": "Complete concept",
        "script": {"text": "Complete script"},
        "scene_plan": [{"scene": 1}],
        "narration_artifact_id": "narration-1",
        "storyboard": [{"scene": 1, "frame": "frame-1"}],
        "preview_artifact_ids": ["preview-1"],
        "spend_estimate": 12.5,
        "spend_ceiling": 15.0,
        "premium_artifact_ids": ["premium-1"],
        "final_video_artifact_id": "final-1",
        "package_manifest": {"facebook": "package-1"},
        "delivery_request": {"scheduled_for": "2026-08-02T12:00:00Z"},
        "delivery_result": {"platform_post_id": "post-1"},
    }
    stage = ProductionStage.CONCEPT_DRAFT
    workflow_status = WorkflowStatus.ACTIVE
    version_status = WorkflowVersionStatus.WORKING
    visited = [stage]

    while stage != ProductionStage.PUBLISHED:
        if version_status == WorkflowVersionStatus.WORKING:
            plan = submit_plan(
                stage=stage,
                workflow_status=workflow_status,
                version_status=version_status,
                snapshot=snapshot,
            )
            stage = plan.to_stage
            workflow_status = plan.workflow_status
            version_status = plan.version_status
        else:
            plan = review_plan(
                stage=stage,
                workflow_status=workflow_status,
                version_status=version_status,
                decision=ReviewDecision.APPROVED,
                snapshot=snapshot,
                reviewer="reviewer.one",
                last_edited_by="producer.one",
            )
            stage = plan.to_stage
            workflow_status = plan.workflow_status
            version_status = (
                WorkflowVersionStatus.WORKING
                if plan.create_successor
                else plan.version_status
            )
        visited.append(stage)
        assert len(visited) <= 30, "workflow path did not converge"

    assert workflow_status == WorkflowStatus.COMPLETED
    assert version_status == WorkflowVersionStatus.APPROVED
    assert visited == [
        ProductionStage.CONCEPT_DRAFT,
        ProductionStage.CONCEPT_REVIEW,
        ProductionStage.SCRIPT_DRAFT,
        ProductionStage.SCRIPT_REVIEW,
        ProductionStage.NARRATION_GENERATION,
        ProductionStage.NARRATION_REVIEW,
        ProductionStage.STORYBOARD_GENERATION,
        ProductionStage.STORYBOARD_REVIEW,
        ProductionStage.LOCAL_PREVIEW_GENERATION,
        ProductionStage.LOCAL_PREVIEW_REVIEW,
        ProductionStage.SPEND_PREPARATION,
        ProductionStage.SPEND_APPROVAL,
        ProductionStage.PREMIUM_PRODUCTION,
        ProductionStage.FINAL_ASSEMBLY,
        ProductionStage.FINAL_REVIEW,
        ProductionStage.PACKAGE_PREPARATION,
        ProductionStage.PACKAGE_APPROVAL,
        ProductionStage.SCHEDULING,
        ProductionStage.PUBLICATION,
        ProductionStage.PUBLISHED,
    ]
