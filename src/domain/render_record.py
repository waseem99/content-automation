from datetime import datetime
from uuid import UUID

from src.domain.render_manifest_models import RenderManifestCreate


class RenderManifest(RenderManifestCreate):
    id: UUID
    created_at: datetime
