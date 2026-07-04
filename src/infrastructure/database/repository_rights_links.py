from __future__ import annotations

from uuid import UUID

from psycopg import Connection


class AssetRightsEvidenceLinkRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(
        self,
        *,
        asset_rights_id: UUID,
        rights_evidence_id: UUID,
        evidence_role: str,
        linked_by: str,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.asset_rights_evidence_links (
                asset_rights_id,
                rights_evidence_id,
                evidence_role,
                linked_by
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (asset_rights_id, rights_evidence_id) DO NOTHING
            RETURNING *
            """,
            (asset_rights_id, rights_evidence_id, evidence_role, linked_by),
        ).fetchone()
        if row:
            return row
        existing = self.conn.execute(
            """
            SELECT *
            FROM football_brief.asset_rights_evidence_links
            WHERE asset_rights_id = %s AND rights_evidence_id = %s
            """,
            (asset_rights_id, rights_evidence_id),
        ).fetchone()
        if existing is None:
            raise RuntimeError("Rights evidence link was not persisted")
        return existing

    def list_for_rights(self, asset_rights_id: UUID) -> list[dict]:
        return self.conn.execute(
            """
            SELECT link.*, evidence.evidence_asset_id, evidence.asset_id
            FROM football_brief.asset_rights_evidence_links AS link
            JOIN football_brief.rights_evidence AS evidence
              ON evidence.id = link.rights_evidence_id
            WHERE link.asset_rights_id = %s
            ORDER BY link.created_at, link.rights_evidence_id
            """,
            (asset_rights_id,),
        ).fetchall()

    def evidence_ids(self, asset_rights_id: UUID) -> tuple[UUID, ...]:
        rows = self.list_for_rights(asset_rights_id)
        return tuple(row["rights_evidence_id"] for row in rows)

    def count_for_rights(self, asset_rights_id: UUID) -> int:
        row = self.conn.execute(
            """
            SELECT count(*) AS total
            FROM football_brief.asset_rights_evidence_links
            WHERE asset_rights_id = %s
            """,
            (asset_rights_id,),
        ).fetchone()
        return int(row["total"])
