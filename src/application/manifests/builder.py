from __future__ import annotations

from src.application.manifests.canonical import manifest_hash, material_input_hash
from src.application.manifests.evidence import ManifestEvidenceLoader
from src.application.manifests.models import RenderManifestBuildRequest
from src.application.manifests.validation import (
    validate_asset_roles,
    validate_brand_version,
    validate_policy_version,
)
from src.domain.render_manifest_models import (
    RenderManifestCreate,
    RenderManifestDocument,
    RenderManifestRecord,
)
from src.domain.render_status import RenderMode
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


PREVIEW_WATERMARK = "PREVIEW - NOT FOR PUBLICATION"


class RenderManifestBuilder:
    def __init__(self, database: Database) -> None:
        self.database = database

    def build(self, request: RenderManifestBuildRequest) -> RenderManifestRecord:
        validate_asset_roles(request)
        with unit_of_work(self.database) as uow:
            evidence = ManifestEvidenceLoader(uow)
            evidence.validate_workflow(request)
            validate_brand_version(
                uow.conn,
                request.brand.version,
                request.brand.content_hash,
            )
            validate_policy_version(
                uow.conn,
                request.policy.version,
                request.policy.content_hash,
            )
            approval = evidence.load_approval(request)
            rights, decision_by_asset = evidence.load_rights(request)
            assets = evidence.enrich_assets(request, decision_by_asset)
            rights_disclosures = evidence.disclosures_from_rights(decision_by_asset)
            disclosures = self._merge_disclosures(request.disclosures, rights_disclosures)

            next_version, parent_id = uow.render_manifests.reserve_next_version(
                request.workflow_run_id
            )
            document = self._document(
                request=request,
                manifest_version=next_version,
                assets=assets,
                disclosures=disclosures,
                rights=rights,
                approval=approval,
            )
            material_hash = material_input_hash(document)
            existing = uow.render_manifests.find_by_material_hash(
                workflow_run_id=request.workflow_run_id,
                mode=request.mode.value,
                platform=request.platform,
                aspect_ratio=request.aspect_ratio,
                material_input_hash=material_hash,
            )
            if existing is not None:
                return existing

            created = uow.render_manifests.create_draft(
                RenderManifestCreate(
                    document=document,
                    parent_manifest_id=parent_id,
                    material_input_hash=material_hash,
                    manifest_hash=manifest_hash(document),
                )
            )
            for asset in assets:
                uow.render_manifests.add_asset(created.id, asset)

            if request.mode == RenderMode.PREVIEW:
                result = uow.render_manifests.seal_preview(created.id)
            else:
                assert approval is not None
                result = uow.render_manifests.approve_publish(
                    manifest_id=created.id,
                    review_id=approval.human_review_id,
                    reviewer=approval.reviewer,
                    approved_at=approval.approved_at,
                )

            uow.workflow_events.create(
                workflow_run_id=request.workflow_run_id,
                stage_execution_id=None,
                event_type="render_manifest_created",
                actor=request.created_by,
                reason=request.mode.value,
                payload={
                    "render_manifest_id": str(result.id),
                    "manifest_version": result.document.manifest_version,
                    "manifest_hash": result.manifest_hash,
                    "mode": request.mode.value,
                },
            )
            return result

    @staticmethod
    def _document(
        *,
        request: RenderManifestBuildRequest,
        manifest_version: int,
        assets,
        disclosures,
        rights,
        approval,
    ) -> RenderManifestDocument:
        is_preview = request.mode == RenderMode.PREVIEW
        output_metadata = {
            "NOT_FOR_PUBLICATION": is_preview,
            "publication_eligible": not is_preview,
            "watermark_required": is_preview,
            "hook_starts_at_frame_one": request.preset.hook_starts_at_frame_one,
            "pre_hook_intro_duration_sec": request.preset.pre_hook_intro_duration_sec,
            "logo_sting_duration_sec": request.preset.logo_sting_duration_sec,
            "logo_sting_placement": request.preset.logo_sting_placement,
        }
        return RenderManifestDocument(
            content_item_id=request.content_item_id,
            workflow_run_id=request.workflow_run_id,
            manifest_version=manifest_version,
            mode=request.mode,
            platform=request.platform.lower(),
            aspect_ratio=request.aspect_ratio,
            script=request.script,
            storyboard=request.storyboard,
            brand=request.brand,
            policy=request.policy,
            preset=request.preset,
            voice_asset_id=request.voice_asset_id,
            music_asset_id=request.music_asset_id,
            assets=assets,
            disclosures=disclosures,
            rights_evaluation=rights,
            approval=approval,
            not_for_publication=is_preview,
            watermark_text=PREVIEW_WATERMARK if is_preview else None,
            output_metadata=output_metadata,
        )

    @staticmethod
    def _merge_disclosures(first, second):
        by_code = {item.code: item for item in (*first, *second)}
        return tuple(by_code[key] for key in sorted(by_code))
