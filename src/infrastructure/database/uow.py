from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from psycopg import Connection

from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_assets import AssetRepository, AssetRightsRepository
from src.infrastructure.database.repository_content import ContentItemRepository
from src.infrastructure.database.repository_evidence import RightsEvidenceRepository
from src.infrastructure.database.repository_manifests import RenderManifestRepository
from src.infrastructure.database.repository_narration import NarrationOutputRepository
from src.infrastructure.database.repository_release_refs import ReleaseReferenceRepository
from src.infrastructure.database.repository_render_jobs import RenderJobRepository
from src.infrastructure.database.repository_rights_decisions import RightsGateEvaluationRepository
from src.infrastructure.database.repository_rights_links import AssetRightsEvidenceLinkRepository
from src.infrastructure.database.repository_rights_state import RightsStateRepository
from src.infrastructure.database.repository_voices import ApprovedVoiceRepository
from src.infrastructure.database.repository_workflow_events import WorkflowEventRepository
from src.infrastructure.database.repository_workflows import StageExecutionRepository, WorkflowRunRepository


@dataclass(slots=True)
class PostgresUnitOfWork:
    conn: Connection[dict]
    content_items: ContentItemRepository = field(init=False)
    assets: AssetRepository = field(init=False)
    asset_rights: AssetRightsRepository = field(init=False)
    rights_state: RightsStateRepository = field(init=False)
    rights_evidence: RightsEvidenceRepository = field(init=False)
    rights_evidence_links: AssetRightsEvidenceLinkRepository = field(init=False)
    rights_gate_evaluations: RightsGateEvaluationRepository = field(init=False)
    approved_voices: ApprovedVoiceRepository = field(init=False)
    workflow_runs: WorkflowRunRepository = field(init=False)
    stage_executions: StageExecutionRepository = field(init=False)
    workflow_events: WorkflowEventRepository = field(init=False)
    render_manifests: RenderManifestRepository = field(init=False)
    render_jobs: RenderJobRepository = field(init=False)
    release_references: ReleaseReferenceRepository = field(init=False)
    narration_outputs: NarrationOutputRepository = field(init=False)

    def __post_init__(self) -> None:
        self.content_items = ContentItemRepository(self.conn)
        self.assets = AssetRepository(self.conn)
        self.asset_rights = AssetRightsRepository(self.conn)
        self.rights_state = RightsStateRepository(self.conn)
        self.rights_evidence = RightsEvidenceRepository(self.conn)
        self.rights_evidence_links = AssetRightsEvidenceLinkRepository(self.conn)
        self.rights_gate_evaluations = RightsGateEvaluationRepository(self.conn)
        self.approved_voices = ApprovedVoiceRepository(self.conn)
        self.workflow_runs = WorkflowRunRepository(self.conn)
        self.stage_executions = StageExecutionRepository(self.conn)
        self.workflow_events = WorkflowEventRepository(self.conn)
        self.render_manifests = RenderManifestRepository(self.conn)
        self.render_jobs = RenderJobRepository(self.conn)
        self.release_references = ReleaseReferenceRepository(self.conn)
        self.narration_outputs = NarrationOutputRepository(self.conn)


@contextmanager
def unit_of_work(database: Database) -> Iterator[PostgresUnitOfWork]:
    with database.transaction() as conn:
        yield PostgresUnitOfWork(conn)
