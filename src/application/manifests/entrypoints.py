from __future__ import annotations

from uuid import UUID

from src.application.manifests.exceptions import ManifestValidationError
from src.application.manifests.renderer import ManifestRendererAdapter, RendererCallback
from src.domain.render_status import RenderMode
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class PreviewRenderEntryPoint:
    def __init__(self, database: Database, renderer: ManifestRendererAdapter) -> None:
        self.database = database
        self.renderer = renderer

    def render(self, manifest_id: UUID, callback: RendererCallback) -> dict:
        self._require_mode(manifest_id, RenderMode.PREVIEW)
        return self.renderer.start(manifest_id, callback)

    def _require_mode(self, manifest_id: UUID, expected: RenderMode) -> None:
        with unit_of_work(self.database) as uow:
            record = uow.render_manifests.get(manifest_id)
        if record.document.mode != expected:
            raise ManifestValidationError(
                f"Manifest {manifest_id} is not a {expected.value} manifest"
            )


class PublishRenderEntryPoint:
    def __init__(self, database: Database, renderer: ManifestRendererAdapter) -> None:
        self.database = database
        self.renderer = renderer

    def render(self, manifest_id: UUID, callback: RendererCallback) -> dict:
        with unit_of_work(self.database) as uow:
            record = uow.render_manifests.get(manifest_id)
        if record.document.mode != RenderMode.PUBLISH:
            raise ManifestValidationError(
                f"Manifest {manifest_id} is not a publish manifest"
            )
        return self.renderer.start(manifest_id, callback)
