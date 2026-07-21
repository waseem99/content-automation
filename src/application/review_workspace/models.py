from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReviewTarget(StrEnum):
    WORKFLOW_VERSION = "workflow_version"
    SCRIPT_VERSION = "script_version"
    SCRIPT_SECTION = "script_section"
    AUDIO_MIX_VERSION = "audio_mix_version"
    AUDIO_PARAGRAPH = "audio_paragraph"
    VISUAL_SHOT_VERSION = "visual_shot_version"
    VISUAL_CANDIDATE = "visual_candidate"


class CommentType(StrEnum):
    GENERAL = "general"
    CHANGE_REQUEST = "change_request"
    FACTUAL = "factual"
    TONE = "tone"
    TIMING = "timing"
    CONTINUITY = "continuity"
    ACCESSIBILITY = "accessibility"
    RIGHTS = "rights"


class TaskType(StrEnum):
    WORKFLOW_UPDATE = "workflow_update"
    SCRIPT_EDIT = "script_edit"
    FACTUAL_SUPPORT = "factual_support"
    TONE_EDIT = "tone_edit"
    AUDIO_RETAKE = "audio_retake"
    AUDIO_MIX = "audio_mix"
    VISUAL_PROMPT = "visual_prompt"
    VISUAL_CANDIDATE = "visual_candidate"
    ACCESSIBILITY = "accessibility"
    RIGHTS = "rights"
    GENERAL = "general"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RevisionTaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RevisionTaskRequest(BaseModel):
    task_type: TaskType
    title: str = Field(min_length=3, max_length=300)
    instructions: str = Field(min_length=3, max_length=5000)
    assignee_operator_id: str = Field(min_length=3, max_length=120)
    due_at: datetime | None = None
    priority: Priority = Priority.NORMAL
    blocker: bool = True


class ReviewCommentRequest(BaseModel):
    target_type: ReviewTarget
    target_id: UUID
    comment_type: CommentType = CommentType.GENERAL
    body: str = Field(min_length=1, max_length=5000)
    blocking: bool = False
    timeline_start_ms: int | None = Field(default=None, ge=0)
    timeline_end_ms: int | None = Field(default=None, ge=1)
    revision_task: RevisionTaskRequest | None = None

    @model_validator(mode="after")
    def validate_comment_contract(self) -> "ReviewCommentRequest":
        has_start = self.timeline_start_ms is not None
        has_end = self.timeline_end_ms is not None
        if has_start != has_end:
            raise ValueError("timeline_start_ms and timeline_end_ms must be supplied together")
        if has_start:
            if self.target_type != ReviewTarget.AUDIO_MIX_VERSION:
                raise ValueError("timed comments require an exact audio mix version")
            if int(self.timeline_end_ms) <= int(self.timeline_start_ms):
                raise ValueError("timeline_end_ms must be greater than timeline_start_ms")
        if self.blocking and self.comment_type != CommentType.CHANGE_REQUEST:
            raise ValueError("blocking comments must be change requests")
        if self.comment_type == CommentType.CHANGE_REQUEST and self.revision_task is None:
            raise ValueError("change requests require a structured revision task")
        if self.comment_type != CommentType.CHANGE_REQUEST and self.revision_task is not None:
            raise ValueError("revision tasks can be created only from change requests")
        return self


class InboxFilters(BaseModel):
    brand_ids: tuple[UUID, ...] = ()
    stages: tuple[str, ...] = ()
    assignee_operator_id: str | None = Field(default=None, max_length=120)
    due_from: datetime | None = None
    due_to: datetime | None = None
    statuses: tuple[str, ...] = ()
    blocker: bool | None = None
    overdue: bool | None = None
    item_types: tuple[str, ...] = ()
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_due_window(self) -> "InboxFilters":
        if self.due_from and self.due_to and self.due_to < self.due_from:
            raise ValueError("due_to cannot be earlier than due_from")
        return self


class CompareTarget(BaseModel):
    target_type: ReviewTarget
    current_id: UUID
    previous_id: UUID | None = None


class TaskMutationRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    actor_note: str | None = Field(default=None, max_length=1000)
    status: RevisionTaskStatus | None = None
    assignee_operator_id: str | None = Field(default=None, min_length=3, max_length=120)
    due_at: datetime | None = None
    clear_due_at: bool = False
    priority: Priority | None = None
    blocker: bool | None = None

    @model_validator(mode="after")
    def exactly_one_mutation(self) -> "TaskMutationRequest":
        dimensions = sum(
            value
            for value in (
                self.status is not None,
                self.assignee_operator_id is not None,
                self.due_at is not None or self.clear_due_at,
                self.priority is not None,
                self.blocker is not None,
            )
        )
        if dimensions != 1:
            raise ValueError("exactly one task field can change per mutation")
        if self.due_at is not None and self.clear_due_at:
            raise ValueError("due_at and clear_due_at are mutually exclusive")
        return self


class ComparisonPair(BaseModel):
    target_type: ReviewTarget
    current: dict[str, Any]
    previous: dict[str, Any] | None
    differences: list[dict[str, Any]]
