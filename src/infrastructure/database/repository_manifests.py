from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from src.domain.render_manifest_models import (
    ManifestAssetReference,
    RenderManifestCreate,
    RenderManifestDocument,
    RenderManifestRecord,
)
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

    def find_by_material_hash(
        self,
        *,
        workflow_run_id: UUID,
        mode: str,
        platform: str,
        aspect_ratio: str,
        material_input_hash: str,
    ) -> RenderManifestRecord | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM football_brief.render_manifests
            WHERE workflow_run_id = %s
              AND mode = %s
              AND platform = %s
              AND aspect_ratio = %s
              AND material_input_hash = %s
              AND status IN ('sealed', 'approved')
            ORDER BY manifest_version DESC
            LIMIT 1
            """,
            (workflow_run_id, mode, platform, aspect_ratio, material_input_hash),
        ).fetchone()
        return self._record(row) if row else None

    def create_draft(self, data: RenderManifestCreate) -> RenderManifestRecord:
        document = data.document
        row = self.conn.execute(
            """
            INSERT INTO football_brief.render_manifests (
                content_item_id, workflow_run_id, manifest_version, mode,
                platform, aspect_ratio, script_version, storyboard_version,
                brand_version, policy_version, ai_disclosure_required,
                ai_disclosure_reason, manifest, manifest_hash,
                parent_manifest_id, schema_version, status,
                material_input_hash, script_hash, storyboard_hash,
                brand_hash, policy_hash, rights_gate_evaluation_id,
                not_for_publication, watermark_text, output_metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            ) RETURNING *
            """,
            (
                document.content_item_id,
                document.workflow_run_id,
                document.manifest_version,
                document.mode.value,
                document.platform,
                document.aspect_ratio,
                document.script.version,
                document.storyboard.version,
                document.brand.version,
                document.policy.version,
                any(item.required for item in document.disclosures),
                ",".join(item.code for item in document.disclosures if item.required) or None,
                Jsonb(document.model_dump(mode="json")),
                data.manifest_hash,
                data.parent_manifest_id,
                document.schema_version,
                data.material_input_hash,
                document.script.content_hash,
                document.storyboard.content_hash,
                document.brand.content_hash,
                document.policy.content_hash,
                document.rights_evaluation.evaluation_id if document.rights_evaluation else None,
                document.not_for_publication,
                document.watermark_text,
                Jsonb(document.output_metadata),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("Render manifest draft was not persisted")
        return self._record(row)

    def add_asset(self, manifest_id: UUID, asset: ManifestAssetReference) -> None:
        if asset.asset_id is None or asset.asset_sha256 is None:
            return
        self.conn.execute(
            """
            INSERT INTO football_brief.render_manifest_assets (
                render_manifest_id, asset_id, asset_rights_id, asset_sha256,
                asset_role, sequence_number, rights_evidence_ids, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                manifest_id,
                asset.asset_id,
                asset.asset_rights_id,
                asset.asset_sha256,
                asset.role.value,
                asset.sequence_number,
                list(asset.rights_evidence_ids),
                Jsonb(asset.metadata),
            ),
        )

    def seal_preview(self, manifest_id: UUID) -> RenderManifestRecord:
        row = self.conn.execute(
            """
            UPDATE football_brief.render_manifests
            SET status = 'sealed'
            WHERE id = %s AND mode = 'preview' AND status = 'draft'
            RETURNING *
            """,
            (manifest_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Preview manifest could not be sealed")
        return self._record(row)

    def approve_publish(
        self,
        *,
        manifest_id: UUID,
        review_id: UUID,
        reviewer: str,
        approved_at: datetime,
    ) -> RenderManifestRecord:
        row = self.conn.execute(
            """
            UPDATE football_brief.render_manifests
            SET status = 'approved',
                approval_review_id = %s,
                approved_by = %s,
                approved_at = %s
            WHERE id = %s AND mode = 'publish' AND status = 'draft'
            RETURNING *
            """,
            (review_id, reviewer, approved_at, manifest_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("Publish manifest could not be approved")
        return self._record(row)

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
            SELECT * FROM football_brief.render_manifest_assets
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
