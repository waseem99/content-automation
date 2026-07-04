from __future__ import annotations

from uuid import UUID

from psycopg import Connection

from src.domain.render_manifest_models import RenderManifestDocument, RenderManifestRecord
from src.domain.render_status import RenderManifestStatus


class RenderManifestRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def reserve_next_version(self, workflow_run_id: UUID) -> tuple[int, UUID | None]:
        self.conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"render-manifest:{workflow_run_id}",),
        )
        row = self.conn.execute(
            """
            SELECT id, manifest_version
            FROM football_brief.render_manifests
            WHERE workflow_run_id = %s
            ORDER BY manifest_version DESC
            LIMIT 1
            """,
            (workflow_run_id,),
        ).fetchone()
        if row is None:
            return 1, None
        return int(row["manifest_version"]) + 1, row["id"]

    def get(self, manifest_id: UUID) -> RenderManifestRecord:
        row = self.conn.execute(
            "SELECT * FROM football_brief.render_manifests WHERE id = %s",
            (manifest_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Render manifest was not found: {manifest_id}")
        return self._record(row)

    def list_assets(self, manifest_id: UUID) -> list[dict]:
        return self.conn.execute(
            """
            SELECT *
            FROM football_brief.render_manifest_assets
            WHERE render_manifest_id = %s
            ORDER BY sequence_number, asset_role, asset_id
            """,
            (manifest_id,),
        ).fetchall()

    @staticmethod
    def _record(row: dict) -> RenderManifestRecord:
        return RenderManifestRecord(
            id=row["id"],
            document=RenderManifestDocument.model_validate(row["manifest"]),
            parent_manifest_id=row["parent_manifest_id"],
            material_input_hash=row["material_input_hash"],
            manifest_hash=row["manifest_hash"],
            status=RenderManifestStatus(row["status"]),
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            created_at=row["created_at"],
        )
