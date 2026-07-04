from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.workflow_models import (
    StageExecution,
    StageExecutionCreate,
    WorkflowRun,
    WorkflowRunCreate,
)
from src.infrastructure.database.repository_base import BaseRepository


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
        return self.required(row, WorkflowRun, "workflow run")

    def get(self, workflow_run_id: UUID) -> WorkflowRun:
        row = self.conn.execute(
            "SELECT * FROM football_brief.workflow_runs WHERE id = %s",
            (workflow_run_id,),
        ).fetchone()
        return self.required(row, WorkflowRun, "workflow run")


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
        return self.required(row, StageExecution, "stage execution")

    def get(self, stage_execution_id: UUID) -> StageExecution:
        row = self.conn.execute(
            "SELECT * FROM football_brief.stage_executions WHERE id = %s",
            (stage_execution_id,),
        ).fetchone()
        return self.required(row, StageExecution, "stage execution")
