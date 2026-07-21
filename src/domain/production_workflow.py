"""Deterministic transition rules for the versioned production workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class ProductionStage(StrEnum):
    CONCEPT_DRAFT = "concept_draft"
    CONCEPT_REVIEW = "concept_review"
    SCRIPT_DRAFT = "script_draft"
    SCRIPT_REVIEW = "script_review"
    NARRATION_GENERATION = "narration_generation"
    NARRATION_REVIEW = "narration_review"
    STORYBOARD_GENERATION = "storyboard_generation"
    STORYBOARD_REVIEW = "storyboard_review"
    LOCAL_PREVIEW_GENERATION = "local_preview_generation"
    LOCAL_PREVIEW_REVIEW = "local_preview_review"
    SPEND_APPROVAL = "spend_approval"
    PREMIUM_PRODUCTION = "premium_production"
    FINAL_ASSEMBLY = "final_assembly"
    FINAL_REVIEW = "final_review"
    PACKAGE_PREPARATION = "package_preparation"
    PACKAGE_APPROVAL = "package_approval"
    SCHEDULING = "scheduling"
    PUBLICATION = "publication"
    PUBLISHED = "published"


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class WorkflowVersionStatus(StrEnum):
    WORKING = "working"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class WorkflowRuleError(ValueError):
    def __init__(self, code: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


WORK_SUBMIT_TARGET: dict[ProductionStage, ProductionStage] = {
    ProductionStage.CONCEPT_DRAFT: ProductionStage.CONCEPT_REVIEW,
    ProductionStage.SCRIPT_DRAFT: ProductionStage.SCRIPT_REVIEW,
    ProductionStage.NARRATION_GENERATION: ProductionStage.NARRATION_REVIEW,
    ProductionStage.STORYBOARD_GENERATION: ProductionStage.STORYBOARD_REVIEW,
    ProductionStage.LOCAL_PREVIEW_GENERATION: ProductionStage.LOCAL_PREVIEW_REVIEW,
    ProductionStage.PREMIUM_PRODUCTION: ProductionStage.FINAL_ASSEMBLY,
    ProductionStage.FINAL_ASSEMBLY: ProductionStage.FINAL_REVIEW,
    ProductionStage.PACKAGE_PREPARATION: ProductionStage.PACKAGE_APPROVAL,
    ProductionStage.SCHEDULING: ProductionStage.PUBLICATION,
}

REVIEW_APPROVAL_TARGET: dict[ProductionStage, ProductionStage] = {
    ProductionStage.CONCEPT_REVIEW: ProductionStage.SCRIPT_DRAFT,
    ProductionStage.SCRIPT_REVIEW: ProductionStage.NARRATION_GENERATION,
    ProductionStage.NARRATION_REVIEW: ProductionStage.STORYBOARD_GENERATION,
    ProductionStage.STORYBOARD_REVIEW: ProductionStage.LOCAL_PREVIEW_GENERATION,
    ProductionStage.LOCAL_PREVIEW_REVIEW: ProductionStage.SPEND_APPROVAL,
    ProductionStage.SPEND_APPROVAL: ProductionStage.PREMIUM_PRODUCTION,
    ProductionStage.FINAL_REVIEW: ProductionStage.PACKAGE_PREPARATION,
    ProductionStage.PACKAGE_APPROVAL: ProductionStage.SCHEDULING,
    ProductionStage.PUBLICATION: ProductionStage.PUBLISHED,
}

REVIEW_REVISION_TARGET: dict[ProductionStage, ProductionStage] = {
    ProductionStage.CONCEPT_REVIEW: ProductionStage.CONCEPT_DRAFT,
    ProductionStage.SCRIPT_REVIEW: ProductionStage.SCRIPT_DRAFT,
    ProductionStage.NARRATION_REVIEW: ProductionStage.NARRATION_GENERATION,
    ProductionStage.STORYBOARD_REVIEW: ProductionStage.STORYBOARD_GENERATION,
    ProductionStage.LOCAL_PREVIEW_REVIEW: ProductionStage.LOCAL_PREVIEW_GENERATION,
    ProductionStage.SPEND_APPROVAL: ProductionStage.LOCAL_PREVIEW_GENERATION,
    ProductionStage.FINAL_REVIEW: ProductionStage.FINAL_ASSEMBLY,
    ProductionStage.PACKAGE_APPROVAL: ProductionStage.PACKAGE_PREPARATION,
    ProductionStage.PUBLICATION: ProductionStage.SCHEDULING,
}

STAGE_REQUIREMENTS: dict[ProductionStage, tuple[str, ...]] = {
    ProductionStage.CONCEPT_DRAFT: ("concept",),
    ProductionStage.CONCEPT_REVIEW: ("concept",),
    ProductionStage.SCRIPT_DRAFT: ("script", "scene_plan"),
    ProductionStage.SCRIPT_REVIEW: ("script", "scene_plan"),
    ProductionStage.NARRATION_GENERATION: ("narration_artifact_id",),
    ProductionStage.NARRATION_REVIEW: ("narration_artifact_id",),
    ProductionStage.STORYBOARD_GENERATION: ("storyboard",),
    ProductionStage.STORYBOARD_REVIEW: ("storyboard",),
    ProductionStage.LOCAL_PREVIEW_GENERATION: ("preview_artifact_ids",),
    ProductionStage.LOCAL_PREVIEW_REVIEW: ("preview_artifact_ids",),
    ProductionStage.SPEND_APPROVAL: ("spend_estimate", "spend_ceiling"),
    ProductionStage.PREMIUM_PRODUCTION: ("premium_artifact_ids",),
    ProductionStage.FINAL_ASSEMBLY: ("final_video_artifact_id",),
    ProductionStage.FINAL_REVIEW: ("final_video_artifact_id",),
    ProductionStage.PACKAGE_PREPARATION: ("package_manifest",),
    ProductionStage.PACKAGE_APPROVAL: ("package_manifest",),
    ProductionStage.SCHEDULING: ("delivery_request",),
    ProductionStage.PUBLICATION: ("delivery_result",),
}

REVIEW_STAGES = frozenset(REVIEW_APPROVAL_TARGET)
WORK_STAGES = frozenset(WORK_SUBMIT_TARGET)

COMPATIBILITY_STAGE: dict[ProductionStage, str] = {
    ProductionStage.CONCEPT_DRAFT: "idea",
    ProductionStage.CONCEPT_REVIEW: "idea",
    ProductionStage.SCRIPT_DRAFT: "script",
    ProductionStage.SCRIPT_REVIEW: "script",
    ProductionStage.NARRATION_GENERATION: "preview",
    ProductionStage.NARRATION_REVIEW: "preview",
    ProductionStage.STORYBOARD_GENERATION: "preview",
    ProductionStage.STORYBOARD_REVIEW: "preview",
    ProductionStage.LOCAL_PREVIEW_GENERATION: "preview",
    ProductionStage.LOCAL_PREVIEW_REVIEW: "preview",
    ProductionStage.SPEND_APPROVAL: "premium",
    ProductionStage.PREMIUM_PRODUCTION: "premium",
    ProductionStage.FINAL_ASSEMBLY: "package",
    ProductionStage.FINAL_REVIEW: "package",
    ProductionStage.PACKAGE_PREPARATION: "package",
    ProductionStage.PACKAGE_APPROVAL: "package",
    ProductionStage.SCHEDULING: "ready",
    ProductionStage.PUBLICATION: "ready",
    ProductionStage.PUBLISHED: "published",
}


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    from_stage: ProductionStage
    to_stage: ProductionStage
    workflow_status: WorkflowStatus
    version_status: WorkflowVersionStatus
    create_revision: bool = False
    create_successor: bool = False
    complete_workflow: bool = False


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def missing_requirements(stage: ProductionStage | str, snapshot: Mapping[str, Any]) -> list[str]:
    value = ProductionStage(stage)
    return [key for key in STAGE_REQUIREMENTS.get(value, ()) if not _present(snapshot.get(key))]


def compatibility_stage(stage: ProductionStage | str, status: WorkflowStatus | str) -> str:
    workflow_status = WorkflowStatus(status)
    if workflow_status == WorkflowStatus.BLOCKED:
        return "blocked"
    if workflow_status == WorkflowStatus.ARCHIVED:
        return "archived"
    return COMPATIBILITY_STAGE[ProductionStage(stage)]


def submit_plan(
    *,
    stage: ProductionStage | str,
    workflow_status: WorkflowStatus | str,
    version_status: WorkflowVersionStatus | str,
    snapshot: Mapping[str, Any],
) -> TransitionPlan:
    current = ProductionStage(stage)
    if WorkflowStatus(workflow_status) != WorkflowStatus.ACTIVE:
        raise WorkflowRuleError("workflow_not_active")
    if WorkflowVersionStatus(version_status) != WorkflowVersionStatus.WORKING:
        raise WorkflowRuleError("version_not_working")
    target = WORK_SUBMIT_TARGET.get(current)
    if target is None:
        raise WorkflowRuleError("stage_not_submittable", details={"stage": current.value})
    missing = missing_requirements(current, snapshot)
    if missing:
        raise WorkflowRuleError("stage_prerequisites_missing", details={"missing": missing})
    target_status = WorkflowVersionStatus.IN_REVIEW if target in REVIEW_STAGES else WorkflowVersionStatus.WORKING
    return TransitionPlan(
        from_stage=current,
        to_stage=target,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=target_status,
    )


def review_plan(
    *,
    stage: ProductionStage | str,
    workflow_status: WorkflowStatus | str,
    version_status: WorkflowVersionStatus | str,
    decision: ReviewDecision | str,
    snapshot: Mapping[str, Any],
    reviewer: str,
    last_edited_by: str,
) -> TransitionPlan:
    current = ProductionStage(stage)
    selected = ReviewDecision(decision)
    if WorkflowStatus(workflow_status) != WorkflowStatus.ACTIVE:
        raise WorkflowRuleError("workflow_not_active")
    if current not in REVIEW_STAGES:
        raise WorkflowRuleError("stage_not_reviewable", details={"stage": current.value})
    if WorkflowVersionStatus(version_status) != WorkflowVersionStatus.IN_REVIEW:
        raise WorkflowRuleError("version_not_in_review")
    if reviewer == last_edited_by:
        raise WorkflowRuleError("independent_review_required")
    if selected == ReviewDecision.APPROVED:
        missing = missing_requirements(current, snapshot)
        if missing:
            raise WorkflowRuleError("stage_prerequisites_missing", details={"missing": missing})
        target = REVIEW_APPROVAL_TARGET[current]
        completed = target == ProductionStage.PUBLISHED
        return TransitionPlan(
            from_stage=current,
            to_stage=target,
            workflow_status=WorkflowStatus.COMPLETED if completed else WorkflowStatus.ACTIVE,
            version_status=WorkflowVersionStatus.APPROVED,
            create_successor=not completed,
            complete_workflow=completed,
        )
    if selected == ReviewDecision.CHANGES_REQUESTED:
        return TransitionPlan(
            from_stage=current,
            to_stage=REVIEW_REVISION_TARGET[current],
            workflow_status=WorkflowStatus.ACTIVE,
            version_status=WorkflowVersionStatus.CHANGES_REQUESTED,
            create_revision=True,
        )
    return TransitionPlan(
        from_stage=current,
        to_stage=current,
        workflow_status=WorkflowStatus.BLOCKED,
        version_status=WorkflowVersionStatus.REJECTED,
    )


def reopen_plan(
    *,
    stage: ProductionStage | str,
    workflow_status: WorkflowStatus | str,
    version_status: WorkflowVersionStatus | str,
) -> TransitionPlan:
    current = ProductionStage(stage)
    if WorkflowStatus(workflow_status) != WorkflowStatus.BLOCKED:
        raise WorkflowRuleError("workflow_not_blocked")
    if WorkflowVersionStatus(version_status) != WorkflowVersionStatus.REJECTED:
        raise WorkflowRuleError("blocked_version_not_rejected")
    target = REVIEW_REVISION_TARGET.get(current)
    if target is None:
        raise WorkflowRuleError("blocked_stage_not_reopenable", details={"stage": current.value})
    return TransitionPlan(
        from_stage=current,
        to_stage=target,
        workflow_status=WorkflowStatus.ACTIVE,
        version_status=WorkflowVersionStatus.WORKING,
        create_revision=True,
    )
