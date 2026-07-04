from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.evidence import RightsEvidenceService
from src.application.assets.models import RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.application.assets.resolver import AssetResolver
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.application.rights.approval import RightsApprovalService
from src.application.rights.gate import RightsGateService
from src.domain.asset_status import AssetSourceType
from src.domain.content_models import ContentItemCreate
from src.domain.evidence_models import RightsEvidenceType
from src.domain.rights_models import AssetRights, AssetRightsCreate
from src.domain.workflow_models import WorkflowRunCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings
from src.infrastructure.database.uow import unit_of_work


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")


def database_fixture():
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=8,
    )
    database = Database(settings)
    database.open(require_schema=False)
    with database.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(database, settings.migrations_dir)
    return database


def close_database(database: Database) -> None:
    with database.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    database.close()


def registry_for(database: Database, root: Path) -> AssetRegistryService:
    resolver = StorageUriResolver(root, root / "data" / "asset_store")
    return AssetRegistryService(database, resolver, ManagedAssetStore(resolver))


def gate_for(database: Database, root: Path) -> RightsGateService:
    registry = registry_for(database, root)
    return RightsGateService(
        database=database,
        asset_resolver=AssetResolver(database, registry.storage_resolver),
    )


def create_workflow(database: Database) -> UUID:
    slug = f"rights-test-{uuid4()}"
    with unit_of_work(database) as uow:
        content = uow.content_items.create(
            ContentItemCreate(
                slug=slug,
                working_title="Rights integration test",
                created_by="pytest",
            )
        )
        workflow = uow.workflow_runs.create(
            WorkflowRunCreate(
                content_item_id=content.id,
                workflow_name="rights-test",
                workflow_version="1",
                input_hash="f" * 64,
            )
        )
    return workflow.id


def register_asset(
    registry: AssetRegistryService,
    path: Path,
    context: AssetContext,
    *,
    metadata: dict | None = None,
):
    classification = AssetClassificationPolicy().classify(context, path)
    return registry.register_file(
        RegisterFileRequest(
            path=path,
            asset_type=classification.asset_type,
            source_type=classification.source_type,
            lifecycle_status=classification.lifecycle_status,
            storage_mode=StorageMode.REFERENCE_IN_PLACE,
            created_by="pytest",
            metadata=metadata or {},
        )
    ).asset


def approve_rights(
    *,
    database: Database,
    registry: AssetRegistryService,
    asset_id: UUID,
    evidence_path: Path,
    platforms: list[str] | None = None,
    territories: list[str] | None = None,
    campaigns: list[str] | None = None,
    commercial_use: bool = True,
    editorial_use: bool = True,
    modification: bool = True,
    synthetic_edit: bool = True,
    attribution_required: bool = False,
    attribution_text: str | None = None,
    valid_from=None,
    expires_at=None,
    review_due_at=None,
    supersedes_rights_id: UUID | None = None,
) -> AssetRights:
    approvals = RightsApprovalService(database)
    rights = approvals.create_pending(
        AssetRightsCreate(
            asset_id=asset_id,
            rights_basis=AssetSourceType.LICENSED,
            supersedes_rights_id=supersedes_rights_id,
            commercial_use_allowed=commercial_use,
            editorial_use_allowed=editorial_use,
            modification_allowed=modification,
            synthetic_edit_allowed=synthetic_edit,
            attribution_required=attribution_required,
            attribution_text=attribution_text,
            platforms=platforms if platforms is not None else ["youtube"],
            territories=territories if territories is not None else ["worldwide"],
            campaigns=campaigns or [],
            valid_from=valid_from,
            expires_at=expires_at,
            review_due_at=review_due_at,
        )
    )
    evidence = RightsEvidenceService(database, registry).register(
        target_asset_id=asset_id,
        evidence_path=evidence_path,
        evidence_type=RightsEvidenceType.LICENSE,
        uploaded_by="pytest",
    )
    approvals.link_evidence(
        rights_id=rights.id,
        evidence_id=evidence.id,
        evidence_role="license",
        linked_by="pytest",
    )
    return approvals.approve(rights_id=rights.id, approved_by="pytest")
