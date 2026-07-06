from __future__ import annotations

from uuid import UUID

from src.application.assets.exceptions import AssetHashMismatch, AssetStorageMissing
from src.application.assets.resolver import AssetResolver
from src.application.lineage.fingerprints import sha256_json
from src.application.quality.checks import fail, manifest_contract_checks, media_checks, render_state_checks
from src.application.quality.media import MetadataMediaInspector
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.domain.quality_models import QualityOutcome, QualityReport, QualityReportCreate
from src.domain.render_status import ManifestAssetRole
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_provider_generation import ProviderGenerationEvidenceRepository
from src.infrastructure.database.repository_quality import QualityReportRepository
from src.infrastructure.database.uow import unit_of_work


MATCH_FOOTAGE_CONTEXTS = {"source_match_video", "extracted_match_clip", "broadcast_match", "match_footage"}


class QualityGateService:
    registry_version = "quality-gate-v1"

    def __init__(self, *, database: Database, resolver: AssetResolver, media_inspector: MetadataMediaInspector | None = None) -> None:
        self.database = database
        self.resolver = resolver
        self.media_inspector = media_inspector or MetadataMediaInspector()

    def evaluate_render_job(self, render_job_id: UUID, *, created_by: str = "quality-gate") -> QualityReport:
        with unit_of_work(self.database) as uow:
            job = uow.render_jobs.get(render_job_id)
            manifest = uow.render_manifests.get(job["render_manifest_id"])
            manifest_assets = uow.render_manifests.list_assets(manifest.id)
            output_hash = None
            inspection = None
            if job["output_asset_id"] is not None:
                output_asset = uow.assets.get(job["output_asset_id"])
                output_hash = output_asset.sha256
                try:
                    resolved = self.resolver.resolve(output_asset.id, verify_hash=True)
                    inspection = self.media_inspector.inspect(resolved.path, output_asset.metadata)
                except (AssetHashMismatch, AssetStorageMissing) as exc:
                    inspection = None
                    extra_checks = [fail("OUTPUT_HASH_MISMATCH", str(exc))]
                else:
                    extra_checks = []
            else:
                extra_checks = []
            checks = [
                *render_state_checks(job, manifest),
                *manifest_contract_checks(manifest),
                *self._asset_checks(uow, manifest_assets),
                *media_checks(inspection, manifest.document.preset),
                *extra_checks,
            ]
            status = self._status(checks, manifest)
            report_hash = sha256_json({
                "render_job_id": str(render_job_id),
                "manifest_hash": manifest.manifest_hash,
                "output_hash": output_hash,
                "checks": checks,
                "status": status.value,
            })
            return QualityReportRepository(uow.conn).create(
                QualityReportCreate(
                    render_job_id=render_job_id,
                    render_manifest_id=manifest.id,
                    output_asset_id=job["output_asset_id"],
                    overall_status=status,
                    checks={"registry_version": self.registry_version, "checks": checks},
                    blocking_failures=[item["code"] for item in checks if item["severity"] == "block"],
                    check_registry_version=self.registry_version,
                    input_hash=manifest.manifest_hash,
                    output_hash=output_hash,
                    report_hash=report_hash,
                    disclosure_texts=[item.text for item in manifest.document.disclosures if item.required] if status == QualityOutcome.PASS_WITH_DISCLOSURE else [],
                    human_review_reasons=[item["code"] for item in checks if item["severity"] == "human_review"],
                    created_by=created_by,
                    metadata={"render_mode": manifest.document.mode.value},
                )
            )

    def _asset_checks(self, uow, manifest_assets: list[dict]) -> list[dict]:
        checks: list[dict] = []
        for row in manifest_assets:
            asset = uow.assets.get(row["asset_id"])
            if asset.sha256 != row["asset_sha256"]:
                checks.append(fail("ASSET_HASH_MISMATCH", "Manifest asset hash does not match registry"))
            try:
                self.resolver.resolve(asset.id, verify_hash=True)
            except (AssetHashMismatch, AssetStorageMissing) as exc:
                checks.append(fail("ASSET_HASH_MISMATCH", str(exc)))
            if asset.lifecycle_status in {AssetLifecycleStatus.DELETED, AssetLifecycleStatus.EXPIRED}:
                checks.append(fail("RIGHTS_NOT_APPROVED", "Manifest asset is unavailable"))
            if row["asset_rights_id"] is None:
                checks.append(fail("RIGHTS_NOT_APPROVED", "Manifest asset has no selected rights"))
            if (asset.metadata or {}).get("asset_context") in MATCH_FOOTAGE_CONTEXTS:
                checks.append(fail("UNAPPROVED_MATCH_FOOTAGE", "Match footage requires explicit rights"))
            if asset.source_type == AssetSourceType.AI_GENERATED:
                evidence = ProviderGenerationEvidenceRepository(uow.conn).get_for_output_asset(asset.id)
                if evidence is None:
                    checks.append(fail("RIGHTS_NOT_APPROVED", "Generated asset lacks provider evidence"))
            if row["asset_role"] == ManifestAssetRole.MUSIC.value and row["asset_rights_id"] is None:
                checks.append(fail("MUSIC_RIGHTS_NOT_APPROVED", "Music rights are not approved"))
            if row["asset_role"] == ManifestAssetRole.FONT.value and row["asset_rights_id"] is None:
                checks.append(fail("FONT_RIGHTS_NOT_APPROVED", "Font rights are not approved"))
        return checks

    def _status(self, checks: list[dict], manifest) -> QualityOutcome:
        if any(item["severity"] == "block" for item in checks):
            return QualityOutcome.BLOCK
        if any(item["severity"] == "human_review" for item in checks):
            return QualityOutcome.HUMAN_REVIEW_REQUIRED
        if any(item.required for item in manifest.document.disclosures):
            return QualityOutcome.PASS_WITH_DISCLOSURE
        return QualityOutcome.PASS
