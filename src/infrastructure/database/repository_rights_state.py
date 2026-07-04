from datetime import datetime
from uuid import UUID

from psycopg import Connection

from src.domain.asset_status import ApprovalStatus
from src.domain.rights_models import AssetRights


class RightsStateRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def get(self, rights_id: UUID) -> AssetRights:
        row = self.conn.execute(
            "SELECT * FROM football_brief.asset_rights WHERE id = %s",
            (rights_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Asset rights record was not found: {rights_id}")
        return AssetRights.model_validate(row)

    def get_optional(self, rights_id: UUID) -> AssetRights | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.asset_rights WHERE id = %s",
            (rights_id,),
        ).fetchone()
        return AssetRights.model_validate(row) if row else None

    def list_unsuperseded_for_asset(self, asset_id: UUID) -> list[AssetRights]:
        rows = self.conn.execute(
            """
            SELECT rights.*
            FROM football_brief.asset_rights AS rights
            WHERE rights.asset_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM football_brief.asset_rights AS newer
                  WHERE newer.supersedes_rights_id = rights.id
              )
            ORDER BY rights.created_at DESC, rights.id DESC
            """,
            (asset_id,),
        ).fetchall()
        return [AssetRights.model_validate(row) for row in rows]

    def get_superseding_records(self, rights_id: UUID) -> list[AssetRights]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM football_brief.asset_rights
            WHERE supersedes_rights_id = %s
            ORDER BY created_at, id
            """,
            (rights_id,),
        ).fetchall()
        return [AssetRights.model_validate(row) for row in rows]

    def transition(
        self,
        *,
        rights_id: UUID,
        status: ApprovalStatus,
        approved_by: str | None = None,
        approved_at: datetime | None = None,
        rejection_reason: str | None = None,
    ) -> AssetRights:
        row = self.conn.execute(
            """
            UPDATE football_brief.asset_rights
            SET approval_status = %s,
                approved_by = %s,
                approved_at = %s,
                rejection_reason = %s
            WHERE id = %s
            RETURNING *
            """,
            (status.value, approved_by, approved_at, rejection_reason, rights_id),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Asset rights record was not found: {rights_id}")
        return AssetRights.model_validate(row)
