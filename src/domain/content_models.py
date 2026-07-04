from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class ContentItemCreate(FrozenRecord):
    slug: str = Field(min_length=1, max_length=200)
    working_title: str = Field(min_length=1, max_length=500)
    lifecycle_status: str = "draft"
    primary_platform: str | None = None
    content_format: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentItem(ContentItemCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
