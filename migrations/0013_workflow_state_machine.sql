-- Football Brief P1: workflow state machine guards and stage dependencies
-- Depends on migrations/0001 through 0012

BEGIN;

CREATE TABLE football_brief.stage_dependencies (
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    upstream_stage_execution_id uuid NOT NULL REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    downstream_stage_execution_id uuid NOT NULL REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    expected_upstream_output_hash char(64),
    created_by text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (upstream_stage_execution_id, downstream_stage_execution_id),
    CHECK (upstream_stage_execution_id <> downstream_stage_execution_id)
);

CREATE INDEX stage_dependencies_workflow_idx
    ON football_brief.stage_dependencies (workflow_run_id);
CREATE INDEX stage_dependencies_downstream_idx
    ON football_brief.stage_dependencies (downstream_stage_execution_id);

CREATE OR REPLACE FUNCTION football_brief.require_state_machine_for_workflow_status()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status
       AND current_setting('football_brief.state_machine', true) IS DISTINCT FROM 'on'
       AND NEW.status <> 'blocked' THEN
        RAISE EXCEPTION 'Workflow status changes must use state machine service';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER workflow_runs_state_machine_guard
BEFORE UPDATE OF status ON football_brief.workflow_runs
FOR EACH ROW EXECUTE FUNCTION football_brief.require_state_machine_for_workflow_status();

CREATE OR REPLACE FUNCTION football_brief.require_state_machine_for_stage_status()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status
       AND current_setting('football_brief.state_machine', true) IS DISTINCT FROM 'on'
       AND NEW.status <> 'awaiting_human' THEN
        RAISE EXCEPTION 'Stage status changes must use state machine service';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER stage_executions_state_machine_guard
BEFORE UPDATE OF status ON football_brief.stage_executions
FOR EACH ROW EXECUTE FUNCTION football_brief.require_state_machine_for_stage_status();

CREATE OR REPLACE FUNCTION football_brief.reject_workflow_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Workflow events are append-only';
END;
$$;

CREATE TRIGGER workflow_events_append_only
BEFORE UPDATE OR DELETE ON football_brief.workflow_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_workflow_event_mutation();

COMMENT ON TABLE football_brief.stage_dependencies IS
    'Explicit dependency graph used by the workflow state machine to supersede stale downstream stages when upstream output hashes change.';

COMMIT;
