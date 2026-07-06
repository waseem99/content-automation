from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.quality_models import QualityReport, QualityReportCreate
from src.infrastructure.database.repository_base import BaseRepository


class QualityReportRepository(BaseRepository[QualityReport]):
    def create(self, data: QualityReportCreate) -> QualityReport:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.quality_reports (
                render_job_id, render_manifest_id, output_asset_id,
                overall_status, checks, blocking_failures,
                check_registry_version, input_hash, output_hash,
                report_hash, disclosure_texts, human_review_reasons,
                created_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.render_job_id,
                data.render_manifest_id,
                data.output_asset_id,
                data.overall_status.value,
                Jsonb(data.checks),
                Jsonb(data.blocking_failures),
                data.check_registry_version,
                data.input_hash,
                data.output_hash,
                data.report_hash,
                Jsonb(data.disclosure_texts),
                Jsonb(data.human_review_reasons),
                data.created_by,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, QualityReport, "quality report")

    def latest_for_job(self, render_job_id: UUID) -> QualityReport | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.quality_reports
            WHERE render_job_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (render_job_id,),
        ).fetchone()
        return QualityReport.model_validate(row) if row else None

    def latest_publishable_for_job(self, render_job_id: UUID) -> QualityReport | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.quality_reports
            WHERE render_job_id = %s
              AND overall_status IN ('pass', 'pass_with_disclosure')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (render_job_id,),
        ).fetchone()
        return QualityReport.model_validate(row) if row else None
