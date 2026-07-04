from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.evidence_models import RightsEvidence, RightsEvidenceCreate
from src.infrastructure.database.repository_base import BaseRepository


class RightsEvidenceRepository(BaseRepository[RightsEvidence]):
    def create(self, data: RightsEvidenceCreate) -> RightsEvidence:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.rights_evidence (
                asset_id,
                evidence_asset_id,
                evidence_type,
                storage_uri,
                sha256,
                source_url,
                metadata,
                uploaded_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (asset_id, evidence_asset_id, evidence_type)
            DO NOTHING
            RETURNING *
            """,
            (
                data.asset_id,
                data.evidence_asset_id,
                data.evidence_type.value,
                data.storage_uri,
                data.sha256,
                data.source_url,
                Jsonb(data.metadata),
                data.uploaded_by,
            ),
        ).fetchone()
        if row:
            return RightsEvidence.model_validate(row)
        existing = self.conn.execute(
            """
            SELECT *
            FROM football_brief.rights_evidence
            WHERE asset_id = %s
              AND evidence_asset_id = %s
              AND evidence_type = %s
            """,
            (data.asset_id, data.evidence_asset_id, data.evidence_type.value),
        ).fetchone()
        return self.required(existing, RightsEvidence, "rights evidence")

    def get(self, evidence_id: UUID) -> RightsEvidence:
        row = self.conn.execute(
            "SELECT * FROM football_brief.rights_evidence WHERE id = %s",
            (evidence_id,),
        ).fetchone()
        return self.required(row, RightsEvidence, "rights evidence")

    def get_by_evidence_asset_id(self, evidence_asset_id: UUID) -> RightsEvidence | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM football_brief.rights_evidence
            WHERE evidence_asset_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (evidence_asset_id,),
        ).fetchone()
        return RightsEvidence.model_validate(row) if row else None

    def list_for_asset(self, asset_id: UUID) -> list[RightsEvidence]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM football_brief.rights_evidence
            WHERE asset_id = %s
            ORDER BY created_at DESC
            """,
            (asset_id,),
        ).fetchall()
        return [RightsEvidence.model_validate(row) for row in rows]
