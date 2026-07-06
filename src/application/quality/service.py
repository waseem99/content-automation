from __future__ import annotations

from uuid import UUID

from src.application.assets.resolver import AssetResolver
from src.application.lineage.fingerprints import sha256_json
from src.application.quality.media import MetadataMediaInspector
from src.domain.quality_models import QualityOutcome, QualityReport, QualityReportCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_quality import QualityReportRepository
from src.infrastructure.database.uow import unit_of_work


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
            output_hash = None
            if job["output_asset_id"] is not None:
                output_asset = uow.assets.get(job["output_asset_id"])
                output_hash = output_asset.sha256
            checks = self._checks(job, manifest)
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

    def _checks(self, job: dict, manifest) -> list[dict]:
        raise NotImplementedError

    def _status(self, checks: list[dict], manifest) -> QualityOutcome:
        if any(item["severity"] == "block" for item in checks):
            return QualityOutcome.BLOCK
        if any(item["severity"] == "human_review" for item in checks):
            return QualityOutcome.HUMAN_REVIEW_REQUIRED
        if any(item.required for item in manifest.document.disclosures):
            return QualityOutcome.PASS_WITH_DISCLOSURE
        return QualityOutcome.PASS
