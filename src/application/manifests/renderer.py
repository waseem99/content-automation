from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from src.application.manifests.exceptions import ManifestRenderError
from src.application.manifests.integrity import ManifestIntegrityVerifier
from src.application.manifests.models import ManifestRenderContext
from src.application.rights.enforcement import RenderStartGuard
from src.application.rights.enums import (
    RightsDecisionOutcome,
    RightsGatePoint,
    RightsPlatform,
)
from src.application.rights.exceptions import RightsGateBlocked, RightsReviewRequired
from src.application.rights.request_models import RightsGateRequest
from src.domain.render_status import RenderMode
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


RendererCallback = Callable[[ManifestRenderContext], UUID | None]


class ManifestRendererAdapter:
    def __init__(
        self,
        *,
        database: Database,
        integrity: ManifestIntegrityVerifier,
        render_start_guard: RenderStartGuard,
    ) -> None:
        self.database = database
        self.integrity = integrity
        self.render_start_guard = render_start_guard

    def start(self, manifest_id: UUID, renderer: RendererCallback) -> dict:
        record, resolved_paths = self.integrity.verify(manifest_id)
        document = record.document

        if document.mode == RenderMode.PUBLISH:
            decision = self.render_start_guard.revalidate(self._rights_request(record))
            if decision.outcome == RightsDecisionOutcome.BLOCK:
                raise RightsGateBlocked(decision.evaluation_id, decision.reason_codes)
            if decision.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED:
                raise RightsReviewRequired(decision.evaluation_id, decision.reason_codes)

        with unit_of_work(self.database) as uow:
            job = uow.render_jobs.create(manifest_id)
            job = uow.render_jobs.set_running(job["id"])

        context = ManifestRenderContext(
            manifest_id=manifest_id,
            render_job_id=job["id"],
            mode=document.mode,
            manifest=document.model_dump(mode="json"),
            resolved_asset_paths=resolved_paths,
            placeholders=tuple(
                item.placeholder_key
                for item in document.assets
                if item.placeholder_key is not None
            ),
            output_metadata=document.output_metadata,
        )

        try:
            output_asset_id = renderer(context)
        except Exception as exc:
            with unit_of_work(self.database) as uow:
                uow.render_jobs.set_failed(job["id"], str(exc))
            raise ManifestRenderError(
                f"Renderer failed for manifest {manifest_id}: {exc}"
            ) from exc

        with unit_of_work(self.database) as uow:
            return uow.render_jobs.set_succeeded(job["id"], output_asset_id)

    @staticmethod
    def _rights_request(record) -> RightsGateRequest:
        document = record.document
        rights = document.rights_evaluation
        if rights is None:
            raise ManifestRenderError("Publish manifest is missing rights context")
        requested = set(rights.requested_uses)
        attribution: dict[UUID, str] = {}
        for disclosure in document.disclosures:
            if disclosure.code.startswith("ATTRIBUTION:"):
                attribution[UUID(disclosure.code.split(":", 1)[1])] = disclosure.text
        return RightsGateRequest(
            workflow_run_id=document.workflow_run_id,
            gate_point=RightsGatePoint.RENDER_START,
            asset_ids=tuple(
                item.asset_id for item in document.assets if item.asset_id is not None
            ),
            platform=RightsPlatform(document.platform),
            territory=rights.territory,
            campaign=rights.campaign,
            commercial_use="commercial" in requested,
            editorial_use="editorial" in requested,
            modification="modification" in requested,
            synthetic_edit="synthetic_edit" in requested,
            supplied_attribution=attribution,
            evaluated_by="manifest-renderer",
        )
