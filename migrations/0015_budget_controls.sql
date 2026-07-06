-- Football Brief P1: provider-call cost reconciliation and budget controls
-- Depends on migrations/0001 through 0014

BEGIN;

ALTER TABLE football_brief.provider_calls
    ADD COLUMN IF NOT EXISTS model_id text,
    ADD COLUMN IF NOT EXISTS latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
    ADD COLUMN IF NOT EXISTS error_classification text,
    ADD COLUMN IF NOT EXISTS pricing_profile text,
    ADD COLUMN IF NOT EXISTS budget_policy_version text;

ALTER TABLE football_brief.cost_entries
    ADD COLUMN IF NOT EXISTS pricing_profile text,
    ADD COLUMN IF NOT EXISTS reconciliation_key text,
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS cost_entries_provider_call_category_idx
    ON football_brief.cost_entries (provider_call_id, category)
    WHERE provider_call_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS provider_calls_provider_started_idx
    ON football_brief.provider_calls (provider, started_at DESC);
CREATE INDEX IF NOT EXISTS cost_entries_reconciliation_idx
    ON football_brief.cost_entries (workflow_run_id, reconciliation_key)
    WHERE reconciliation_key IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.apply_cost_entry_totals()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE football_brief.workflow_runs
    SET actual_cost_usd = COALESCE(actual_cost_usd, 0) + NEW.amount_usd
    WHERE id = NEW.workflow_run_id;

    IF NEW.stage_execution_id IS NOT NULL THEN
        UPDATE football_brief.stage_executions
        SET actual_cost_usd = COALESCE(actual_cost_usd, 0) + NEW.amount_usd
        WHERE id = NEW.stage_execution_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER cost_entries_apply_totals
AFTER INSERT ON football_brief.cost_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_cost_entry_totals();

CREATE OR REPLACE FUNCTION football_brief.reject_cost_entry_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Cost entries are append-only';
END;
$$;

CREATE TRIGGER cost_entries_append_only
BEFORE UPDATE OR DELETE ON football_brief.cost_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_cost_entry_mutation();

COMMIT;
