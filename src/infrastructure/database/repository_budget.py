from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.budget_models import CostEntry, CostEntryCreate, ProviderCall, ProviderCallCreate
from src.infrastructure.database.repository_base import BaseRepository


class ProviderCallRepository(BaseRepository[ProviderCall]):
    def create(self, data: ProviderCallCreate) -> ProviderCall:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.provider_calls (
                stage_execution_id, provider, operation, provider_request_id,
                idempotency_key, status, request_fingerprint, response_fingerprint,
                units, unit_name, cost_usd, completed_at, metadata,
                model_id, latency_ms, error_classification, pricing_profile, budget_policy_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      CASE WHEN %s IN ('succeeded','failed','cancelled') THEN now() ELSE NULL END,
                      %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider, idempotency_key) DO UPDATE SET
                provider_request_id = COALESCE(football_brief.provider_calls.provider_request_id, EXCLUDED.provider_request_id)
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
                data.response_fingerprint,
                data.units,
                data.unit_name,
                data.cost_usd,
                data.status.value,
                Jsonb(data.metadata),
                data.model_id,
                data.latency_ms,
                data.error_classification,
                data.pricing_profile,
                data.budget_policy_version,
            ),
        ).fetchone()
        return self.required(row, ProviderCall, "provider call")

    def get_by_provider_key(self, provider: str, idempotency_key: str) -> ProviderCall | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.provider_calls WHERE provider = %s AND idempotency_key = %s",
            (provider, idempotency_key),
        ).fetchone()
        return ProviderCall.model_validate(row) if row else None

    def sum_for_workflow(self, workflow_run_id: UUID) -> str:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(provider_calls.cost_usd), 0)::text AS total
            FROM football_brief.provider_calls provider_calls
            JOIN football_brief.stage_executions stage ON stage.id = provider_calls.stage_execution_id
            WHERE stage.workflow_run_id = %s AND provider_calls.status = 'succeeded'
            """,
            (workflow_run_id,),
        ).fetchone()
        return row["total"]


class CostEntryRepository(BaseRepository[CostEntry]):
    def create(self, data: CostEntryCreate) -> CostEntry:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.cost_entries (
                workflow_run_id, stage_execution_id, provider_call_id, category,
                amount_usd, quantity, unit_name, pricing_profile, reconciliation_key, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider_call_id, category) WHERE provider_call_id IS NOT NULL DO UPDATE SET
                provider_call_id = football_brief.cost_entries.provider_call_id
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
                data.pricing_profile,
                data.reconciliation_key,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, CostEntry, "cost entry")

    def sum_for_workflow(self, workflow_run_id: UUID) -> str:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_usd), 0)::text AS total FROM football_brief.cost_entries WHERE workflow_run_id = %s",
            (workflow_run_id,),
        ).fetchone()
        return row["total"]

    def list_for_workflow(self, workflow_run_id: UUID) -> tuple[CostEntry, ...]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.cost_entries WHERE workflow_run_id = %s ORDER BY created_at ASC",
            (workflow_run_id,),
        ).fetchall()
        return tuple(CostEntry.model_validate(row) for row in rows)
