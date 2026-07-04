"""Unit-of-work boundary binding repositories to one PostgreSQL transaction."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from psycopg import Connection

from src.infrastructure.database.connection import Database
from src.infrastructure.database.repositories import (
    AssetRepository,
    AssetRightsRepository,
    ContentItemRepository,
    CostEntryRepository,
    HumanReviewRepository,
    ProviderCallRepository,
    QualityReportRepository,
    RenderJobRepository,
    RenderManifestRepository,
    StageExecutionRepository,
    WorkflowRunRepository,
)


@dataclass(slots=True)
class PostgresUnitOfWork:
    conn: Connection[dict]
    content_items: ContentItemRepository = field(init=False)
    assets: AssetRepository = field(init=False)
    asset_rights: AssetRightsRepository = field(init=False)
    workflow_runs: WorkflowRunRepository = field(init=False)
    stage_executions: StageExecutionRepository = field(init=False)
    human_reviews: HumanReviewRepository = field(init=False)
    provider_calls: ProviderCallRepository = field(init=False)
    cost_entries: CostEntryRepository = field(init=False)
    render_manifests: RenderManifestRepository = field(init=False)
    render_jobs: RenderJobRepository = field(init=False)
    quality_reports: QualityReportRepository = field(init=False)

    def __post_init__(self) -> None:
        self.content_items = ContentItemRepository(self.conn)
        self.assets = AssetRepository(self.conn)
        self.asset_rights = AssetRightsRepository(self.conn)
        self.workflow_runs = WorkflowRunRepository(self.conn)
        self.stage_executions = StageExecutionRepository(self.conn)
        self.human_reviews = HumanReviewRepository(self.conn)
        self.provider_calls = ProviderCallRepository(self.conn)
        self.cost_entries = CostEntryRepository(self.conn)
        self.render_manifests = RenderManifestRepository(self.conn)
        self.render_jobs = RenderJobRepository(self.conn)
        self.quality_reports = QualityReportRepository(self.conn)


@contextmanager
def unit_of_work(database: Database) -> Iterator[PostgresUnitOfWork]:
    """Run repository operations atomically on one connection."""

    with database.transaction() as conn:
        yield PostgresUnitOfWork(conn)
