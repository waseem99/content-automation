from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.provider_lineage_models import (
    LineageNode,
    LineageReport,
    ProviderGenerationEvidence,
    ProviderGenerationEvidenceCreate,
)
from src.infrastructure.database.repository_base import BaseRepository


class ProviderGenerationEvidenceRepository(BaseRepository[ProviderGenerationEvidence]):
    def create(self, data: ProviderGenerationEvidenceCreate) -> ProviderGenerationEvidence:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.provider_generation_evidence (
                provider_call_id, output_asset_id, parent_asset_id,
                workflow_run_id, stage_execution_id, provider, operation,
                model_id, prompt_name, prompt_version, prompt_hash,
                request_fingerprint, response_fingerprint, provider_request_id,
                input_asset_sha256, output_asset_sha256, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.provider_call_id,
                data.output_asset_id,
                data.parent_asset_id,
                data.workflow_run_id,
                data.stage_execution_id,
                data.provider,
                data.operation,
                data.model_id,
                data.prompt_name,
                data.prompt_version,
                data.prompt_hash,
                data.request_fingerprint,
                data.response_fingerprint,
                data.provider_request_id,
                data.input_asset_sha256,
                data.output_asset_sha256,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, ProviderGenerationEvidence, "provider generation evidence")

    def get_for_output_asset(self, asset_id: UUID) -> ProviderGenerationEvidence | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.provider_generation_evidence
            WHERE output_asset_id = %s
            """,
            (asset_id,),
        ).fetchone()
        return ProviderGenerationEvidence.model_validate(row) if row else None

    def find_reusable(
        self,
        *,
        provider: str,
        operation: str,
        request_fingerprint: str,
        input_asset_sha256: str | None,
    ) -> ProviderGenerationEvidence | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.provider_generation_evidence
            WHERE provider = %s
              AND operation = %s
              AND request_fingerprint = %s
              AND input_asset_sha256 IS NOT DISTINCT FROM %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (provider, operation, request_fingerprint, input_asset_sha256),
        ).fetchone()
        return ProviderGenerationEvidence.model_validate(row) if row else None

    def lineage_for_asset(self, asset_id: UUID) -> LineageReport:
        rows = self.conn.execute(
            """
            WITH RECURSIVE lineage AS (
                SELECT a.*, 0 AS depth
                FROM football_brief.assets a
                WHERE a.id = %s
                UNION ALL
                SELECT parent.*, lineage.depth + 1 AS depth
                FROM football_brief.assets parent
                JOIN lineage ON lineage.parent_asset_id = parent.id
                WHERE lineage.depth < 64
            )
            SELECT
                lineage.id AS asset_id,
                lineage.sha256 AS asset_sha256,
                lineage.asset_type,
                lineage.source_type,
                lineage.parent_asset_id,
                lineage.depth,
                evidence.id AS generation_evidence_id,
                evidence.provider,
                evidence.operation,
                evidence.model_id,
                evidence.provider_request_id,
                evidence.prompt_hash
            FROM lineage
            LEFT JOIN football_brief.provider_generation_evidence evidence
                ON evidence.output_asset_id = lineage.id
            ORDER BY lineage.depth ASC
            """,
            (asset_id,),
        ).fetchall()
        return LineageReport(
            root_asset_id=asset_id,
            nodes=tuple(LineageNode.model_validate(row) for row in rows),
        )
