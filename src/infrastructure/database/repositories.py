"""Explicit PostgreSQL repositories for the Phase 0/1 foundation tables."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Generic, TypeVar
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from src.domain.foundation import (
    Asset,
    AssetCreate,
    AssetRights,
    AssetRightsCreate,
    ContentItem,
    ContentItemCreate,
    CostEntry,
    CostEntryCreate,
    HumanReview,
    HumanReviewCreate,
    ProviderCall,
    ProviderCallCreate,
    QualityReport,
    QualityReportCreate,
    RenderJob,
    RenderJobCreate,
    RenderManifest,
    RenderManifestCreate,
    StageExecution,
    StageExecutionCreate,
    WorkflowRun,
    WorkflowRunCreate,
)


RecordT = TypeVar("RecordT", bound=BaseModel)


class RepositoryError(RuntimeError):
    """Raised when a repository operation cannot satisfy its contract."""


class NotFoundError(RepositoryError):
    """Raised when a required record does not exist."""


class BaseRepository(Generic[RecordT]):
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    @staticmethod
    def _required(row: dict[str, Any] | None, model: type[RecordT], entity: str) -> RecordT:
        if row is None:
            raise NotFoundError(f"{entity} was not found")
        return model.model_validate(row)


class ContentItemRepository(BaseRepository[ContentItem]):
    def create(self, data: ContentItemCreate) -> ContentItem:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.content_items (
                slug, working_title, lifecycle_status, primary_platform,
                content_format, created_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.slug,
                data.working_title,
                data.lifecycle_status,
                data.primary_platform,
                data.content_format,
                data.created_by,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self._required(row, ContentItem, "content item")

    def get(self, content_item_id: UUID) -> ContentItem:
        row = self.conn.execute(
            "SELECT * FROM football_brief.content_items WHERE id = %s",
            (content_item_id,),
        ).fetchone()
        return self._required(row, ContentItem, "content item")

    def get_by_slug(self, slug: str) -> ContentItem | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.content_items WHERE slug = %s", (slug,)
        ).fetchone()
        return ContentItem.model_validate(row) if row else None


class AssetRepository(BaseRepository[Asset]):
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
            (
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
            ),
        ).fetchone()
        return self._required(row, Asset, "asset")

    def get(self, asset_id: UUID) -> Asset:
        row = self.conn.execute(
            "SELECT * FROM football_brief.assets WHERE id = %s", (asset_id,)
        ).fetchone()
        return self._required(row, Asset, "asset")

    def get_by_sha256(self, sha256: str) -> Asset | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.assets WHERE sha256 = %s", (sha256,)
        ).fetchone()
        return Asset.model_validate(row) if row else None

    def create_or_get(self, data: AssetCreate) -> tuple[Asset, bool]:
        existing = self.get_by_sha256(data.sha256)
        if existing:
            return existing, False
        return self.create(data), True


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
            )
            RETURNING *
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
        return self._required(row, AssetRights, "asset rights")

    def get(self, rights_id: UUID) -> AssetRights:
        row = self.conn.execute(
            "SELECT * FROM football_brief.asset_rights WHERE id = %s", (rights_id,)
        ).fetchone()
        return self._required(row, AssetRights, "asset rights")

    def list_for_asset(self, asset_id: UUID) -> list[AssetRights]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.asset_rights "
            "WHERE asset_id = %s ORDER BY created_at DESC",
            (asset_id,),
        ).fetchall()
        return [AssetRights.model_validate(row) for row in rows]


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def create(self, data: WorkflowRunCreate) -> WorkflowRun:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.workflow_runs (
                content_item_id, workflow_name, workflow_version, current_stage,
                input_hash, approved_budget_usd, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.content_item_id,
                data.workflow_name,
                data.workflow_version,
                data.current_stage,
                data.input_hash,
                data.approved_budget_usd,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self._required(row, WorkflowRun, "workflow run")

    def get(self, workflow_run_id: UUID) -> WorkflowRun:
        row = self.conn.execute(
            "SELECT * FROM football_brief.workflow_runs WHERE id = %s",
            (workflow_run_id,),
        ).fetchone()
        return self._required(row, WorkflowRun, "workflow run")


class StageExecutionRepository(BaseRepository[StageExecution]):
    def create(self, data: StageExecutionCreate) -> StageExecution:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.stage_executions (
                workflow_run_id, stage_name, stage_version, status, attempt,
                idempotency_key, input_hash, model_or_tool, prompt_version,
                timeout_seconds, estimated_cost_usd, operator
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.stage_name,
                data.stage_version,
                data.status.value,
                data.attempt,
                data.idempotency_key,
                data.input_hash,
                data.model_or_tool,
                data.prompt_version,
                data.timeout_seconds,
                data.estimated_cost_usd,
                data.operator,
            ),
        ).fetchone()
        return self._required(row, StageExecution, "stage execution")

    def get(self, stage_execution_id: UUID) -> StageExecution:
        row = self.conn.execute(
            "SELECT * FROM football_brief.stage_executions WHERE id = %s",
            (stage_execution_id,),
        ).fetchone()
        return self._required(row, StageExecution, "stage execution")


class HumanReviewRepository(BaseRepository[HumanReview]):
    def create(self, data: HumanReviewCreate) -> HumanReview:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.human_reviews (
                workflow_run_id, stage_execution_id, review_type, decision,
                reviewer, rationale, checklist
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.stage_execution_id,
                data.review_type,
                data.decision,
                data.reviewer,
                data.rationale,
                Jsonb(data.checklist),
            ),
        ).fetchone()
        return self._required(row, HumanReview, "human review")

    def list_for_workflow(self, workflow_run_id: UUID) -> list[HumanReview]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.human_reviews "
            "WHERE workflow_run_id = %s ORDER BY created_at",
            (workflow_run_id,),
        ).fetchall()
        return [HumanReview.model_validate(row) for row in rows]


class ProviderCallRepository(BaseRepository[ProviderCall]):
    def create(self, data: ProviderCallCreate) -> ProviderCall:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.provider_calls (
                stage_execution_id, provider, operation, provider_request_id,
                idempotency_key, status, request_fingerprint, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.stage_execution_id,
                data.provider,
                data.operation,
                data.provider_request_id,
                data.idempotency_key,
                data.status.value,
                data.request_fingerprint,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self._required(row, ProviderCall, "provider call")

    def get_by_idempotency_key(self, provider: str, key: str) -> ProviderCall | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.provider_calls "
            "WHERE provider = %s AND idempotency_key = %s",
            (provider, key),
        ).fetchone()
        return ProviderCall.model_validate(row) if row else None


class CostEntryRepository(BaseRepository[CostEntry]):
    def create(self, data: CostEntryCreate) -> CostEntry:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.cost_entries (
                workflow_run_id, stage_execution_id, provider_call_id,
                category, amount_usd, quantity, unit_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.stage_execution_id,
                data.provider_call_id,
                data.category,
                data.amount_usd,
                data.quantity,
                data.unit_name,
            ),
        ).fetchone()
        return self._required(row, CostEntry, "cost entry")

    def total_for_workflow(self, workflow_run_id: UUID) -> Decimal:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) AS total "
            "FROM football_brief.cost_entries WHERE workflow_run_id = %s",
            (workflow_run_id,),
        ).fetchone()
        return Decimal(row["total"])


class RenderManifestRepository(BaseRepository[RenderManifest]):
    def create(self, data: RenderManifestCreate) -> RenderManifest:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.render_manifests (
                content_item_id, workflow_run_id, manifest_version, mode,
                platform, aspect_ratio, script_version, storyboard_version,
                brand_version, policy_version, ai_disclosure_required,
                ai_disclosure_reason, manifest, manifest_hash, approved_by,
                approved_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
            """,
            (
                data.content_item_id,
                data.workflow_run_id,
                data.manifest_version,
                data.mode.value,
                data.platform,
                data.aspect_ratio,
                data.script_version,
                data.storyboard_version,
                data.brand_version,
                data.policy_version,
                data.ai_disclosure_required,
                data.ai_disclosure_reason,
                Jsonb(data.manifest),
                data.manifest_hash,
                data.approved_by,
                data.approved_at,
            ),
        ).fetchone()
        return self._required(row, RenderManifest, "render manifest")

    def get(self, manifest_id: UUID) -> RenderManifest:
        row = self.conn.execute(
            "SELECT * FROM football_brief.render_manifests WHERE id = %s",
            (manifest_id,),
        ).fetchone()
        return self._required(row, RenderManifest, "render manifest")


class RenderJobRepository(BaseRepository[RenderJob]):
    def create(self, data: RenderJobCreate) -> RenderJob:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.render_jobs (render_manifest_id, status)
            VALUES (%s, %s)
            RETURNING *
            """,
            (data.render_manifest_id, data.status.value),
        ).fetchone()
        return self._required(row, RenderJob, "render job")

    def get(self, render_job_id: UUID) -> RenderJob:
        row = self.conn.execute(
            "SELECT * FROM football_brief.render_jobs WHERE id = %s",
            (render_job_id,),
        ).fetchone()
        return self._required(row, RenderJob, "render job")


class QualityReportRepository(BaseRepository[QualityReport]):
    def create(self, data: QualityReportCreate) -> QualityReport:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.quality_reports (
                render_job_id, overall_status, checks, blocking_failures
            ) VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.render_job_id,
                data.overall_status.value,
                Jsonb(data.checks),
                Jsonb(data.blocking_failures),
            ),
        ).fetchone()
        return self._required(row, QualityReport, "quality report")

    def latest_for_job(self, render_job_id: UUID) -> QualityReport | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.quality_reports "
            "WHERE render_job_id = %s ORDER BY created_at DESC LIMIT 1",
            (render_job_id,),
        ).fetchone()
        return QualityReport.model_validate(row) if row else None
