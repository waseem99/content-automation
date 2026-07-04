from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.asset_models import Asset, AssetCreate
from src.domain.rights_models import AssetRights, AssetRightsCreate
from src.infrastructure.database.repository_base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    @staticmethod
    def _params(data: AssetCreate) -> tuple:
        return (
            data.asset_type.value,
            data.source_type.value,
            data.lifecycle_status.value,
            data.original_filename,
            data.storage_uri,
            data.sha256,
            data.mime_type,
            data.size_bytes,
            data.parent_asset_id,
            Jsonb(data.metadata),
            data.created_by,
        )

    def create(self, data: AssetCreate) -> Asset:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.assets (
                asset_type, source_type, lifecycle_status, original_filename,
                storage_uri, sha256, mime_type, size_bytes, parent_asset_id,
                metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            self._params(data),
        ).fetchone()
        return self.required(row, Asset, "asset")

    def get(self, asset_id: UUID) -> Asset:
        row = self.conn.execute(
            "SELECT * FROM football_brief.assets WHERE id = %s",
            (asset_id,),
        ).fetchone()
        return self.required(row, Asset, "asset")

    def get_optional(self, asset_id: UUID) -> Asset | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.assets WHERE id = %s",
            (asset_id,),
        ).fetchone()
        return Asset.model_validate(row) if row else None

    def get_by_sha256(self, sha256: str) -> Asset | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.assets WHERE sha256 = %s",
            (sha256,),
        ).fetchone()
        return Asset.model_validate(row) if row else None

    def create_or_get(self, data: AssetCreate) -> tuple[Asset, bool]:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.assets (
                asset_type, source_type, lifecycle_status, original_filename,
                storage_uri, sha256, mime_type, size_bytes, parent_asset_id,
                metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sha256) DO NOTHING
            RETURNING *
            """,
            self._params(data),
        ).fetchone()
        if row:
            return Asset.model_validate(row), True
        existing = self.get_by_sha256(data.sha256)
        if existing is None:
            raise RuntimeError("Asset deduplication conflict did not return an existing row")
        return existing, False


class AssetRightsRepository(BaseRepository[AssetRights]):
    def create(self, data: AssetRightsCreate) -> AssetRights:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.asset_rights (
                asset_id, supersedes_rights_id, rights_basis, asset_owner,
                licensor, license_type, license_version, license_url,
                terms_snapshot_uri, terms_snapshot_hash,
                commercial_use_allowed, editorial_use_allowed,
                modification_allowed, synthetic_edit_allowed,
                attribution_required, attribution_text, territories, platforms,
                campaigns, valid_from, expires_at, review_due_at,
                approval_status, approved_by, approved_at, rejection_reason
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            ) RETURNING *
            """,
            (
                data.asset_id,
                data.supersedes_rights_id,
                data.rights_basis.value,
                data.asset_owner,
                data.licensor,
                data.license_type,
                data.license_version,
                data.license_url,
                data.terms_snapshot_uri,
                data.terms_snapshot_hash,
                data.commercial_use_allowed,
                data.editorial_use_allowed,
                data.modification_allowed,
                data.synthetic_edit_allowed,
                data.attribution_required,
                data.attribution_text,
                data.territories,
                data.platforms,
                data.campaigns,
                data.valid_from,
                data.expires_at,
                data.review_due_at,
                data.approval_status.value,
                data.approved_by,
                data.approved_at,
                data.rejection_reason,
            ),
        ).fetchone()
        return self.required(row, AssetRights, "asset rights")

    def list_for_asset(self, asset_id: UUID) -> list[AssetRights]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.asset_rights "
            "WHERE asset_id = %s ORDER BY created_at DESC",
            (asset_id,),
        ).fetchall()
        return [AssetRights.model_validate(row) for row in rows]
