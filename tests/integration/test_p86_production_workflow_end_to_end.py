from __future__ import annotations

from src.application.production_workflow_service import ProductionWorkflowService
from src.domain.production_workflow import ProductionStage, ReviewDecision
from src.infrastructure.database.connection import Database
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded


# Imported fixtures are intentionally re-exported for this module's PostgreSQL lifecycle.
__all__ = ["database", "seeded"]


def test_complete_database_workflow_reaches_published_with_exact_version_history(
    database: Database, seeded: dict[str, object]
) -> None:
    service = ProductionWorkflowService(database)
    producer = str(seeded["producer"])
    reviewer = str(seeded["reviewer"])
    publisher = str(seeded["publisher"])
    admin = str(seeded["admin"])

    workflow_id = service.initialize(
        content_id=seeded["content_id"],
        actor=producer,
    )["workflow_id"]
    lock = 1

    def detail() -> dict:
        return service.detail(workflow_id=workflow_id)

    def update(actor: str, patch: dict) -> dict:
        nonlocal lock
        result = service.update_snapshot(
            workflow_id=workflow_id,
            expected_lock_version=lock,
            patch=patch,
            actor=actor,
        )
        lock += 1
        assert result["workflow"]["lock_version"] == lock
        return result

    def submit(actor: str, expected_stage: ProductionStage) -> dict:
        nonlocal lock
        result = service.submit(
            workflow_id=workflow_id,
            expected_lock_version=lock,
            actor=actor,
            rationale=f"Submit {expected_stage.value}",
        )
        lock += 1
        assert result["workflow"]["current_stage"] == expected_stage.value
        assert result["workflow"]["lock_version"] == lock
        return result

    def approve(actor: str, expected_stage: ProductionStage) -> dict:
        nonlocal lock
        result = service.decide(
            workflow_id=workflow_id,
            expected_lock_version=lock,
            reviewer=actor,
            decision=ReviewDecision.APPROVED,
            rationale=f"Approve into {expected_stage.value}",
        )
        lock += 1
        assert result["workflow"]["current_stage"] == expected_stage.value
        assert result["workflow"]["lock_version"] == lock
        return result

    submit(producer, ProductionStage.CONCEPT_REVIEW)
    approve(reviewer, ProductionStage.SCRIPT_DRAFT)

    update(
        producer,
        {
            "script": {"narration": "A complete evidence-led script."},
            "scene_plan": [{"scene": 1, "purpose": "hook"}],
        },
    )
    submit(producer, ProductionStage.SCRIPT_REVIEW)
    approve(reviewer, ProductionStage.NARRATION_GENERATION)

    update(producer, {"narration_artifact_id": "narration-asset-1"})
    submit(producer, ProductionStage.NARRATION_REVIEW)
    approve(reviewer, ProductionStage.STORYBOARD_GENERATION)

    update(producer, {"storyboard": [{"scene": 1, "frame": "frame-1"}]})
    submit(producer, ProductionStage.STORYBOARD_REVIEW)
    approve(reviewer, ProductionStage.LOCAL_PREVIEW_GENERATION)

    update(producer, {"preview_artifact_ids": ["preview-asset-1"]})
    submit(producer, ProductionStage.LOCAL_PREVIEW_REVIEW)
    approve(reviewer, ProductionStage.SPEND_PREPARATION)

    update(
        producer,
        {
            "spend_estimate": {"currency": "USD", "amount": 12.5},
            "spend_ceiling": {"currency": "USD", "amount": 15.0},
        },
    )
    submit(producer, ProductionStage.SPEND_APPROVAL)
    approve(reviewer, ProductionStage.PREMIUM_PRODUCTION)

    update(producer, {"premium_artifact_ids": ["premium-asset-1"]})
    submit(producer, ProductionStage.FINAL_ASSEMBLY)

    update(producer, {"final_video_artifact_id": "final-video-asset-1"})
    submit(producer, ProductionStage.FINAL_REVIEW)
    approve(reviewer, ProductionStage.PACKAGE_PREPARATION)

    update(
        producer,
        {
            "package_manifest": {
                "facebook": {
                    "video_asset_id": "final-video-asset-1",
                    "caption": "Approved caption",
                }
            }
        },
    )
    submit(producer, ProductionStage.PACKAGE_APPROVAL)
    approve(reviewer, ProductionStage.SCHEDULING)

    update(
        publisher,
        {
            "delivery_request": {
                "platform": "facebook",
                "scheduled_for": "2026-08-02T12:00:00Z",
            },
            "delivery_result": {
                "platform": "facebook",
                "platform_post_id": "post-1",
                "published_at": "2026-08-02T12:00:04Z",
            },
        },
    )
    submit(publisher, ProductionStage.PUBLICATION)
    completed = approve(admin, ProductionStage.PUBLISHED)

    workflow = completed["workflow"]
    assert workflow["status"] == "completed"
    assert workflow["compatibility_stage"] == "published"
    assert workflow["completed_at"] is not None
    assert workflow["content_version"] == 1
    assert len(completed["versions"]) == 9
    assert all(version["status"] == "approved" for version in completed["versions"])
    assert len(completed["decisions"]) == 9
    assert {
        (str(decision["workflow_version_id"]), str(decision["stage"]))
        for decision in completed["decisions"]
    } == {
        (str(version["id"]), stage.value)
        for version, stage in zip(
            reversed(completed["versions"]),
            (
                ProductionStage.CONCEPT_REVIEW,
                ProductionStage.SCRIPT_REVIEW,
                ProductionStage.NARRATION_REVIEW,
                ProductionStage.STORYBOARD_REVIEW,
                ProductionStage.LOCAL_PREVIEW_REVIEW,
                ProductionStage.SPEND_APPROVAL,
                ProductionStage.FINAL_REVIEW,
                ProductionStage.PACKAGE_APPROVAL,
                ProductionStage.PUBLICATION,
            ),
            strict=True,
        )
    }

    final_detail = detail()
    assert final_detail["workflow"]["current_stage"] == ProductionStage.PUBLISHED.value
