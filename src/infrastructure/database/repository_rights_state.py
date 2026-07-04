from uuid import UUID

from psycopg import Connection

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
