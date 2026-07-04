from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord
from src.domain.render_status import RenderMode


class RenderManifestCreate(FrozenRecord):
    content_item_id: UUID
    workflow_run_id: UUID
    mode: RenderMode
    platform: str = Field(min_length=1)
    aspect_ratio: str = Field(min_length=1)
    brand_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    manifest: dict[str, Any]
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
