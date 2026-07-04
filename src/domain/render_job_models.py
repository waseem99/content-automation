from datetime import datetime
from uuid import UUID

from src.domain.base import FrozenRecord
from src.domain.render_status import RenderJobStatus


class RenderJobCreate(FrozenRecord):
    render_manifest_id: UUID
    status: RenderJobStatus = RenderJobStatus.PENDING


class RenderJob(RenderJobCreate):
    id: UUID
    output_asset_id: UUID | None = None
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
