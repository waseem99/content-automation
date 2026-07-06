BEGIN;

CREATE TABLE football_brief.source_output_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    source_output_id uuid NOT NULL,
    packet_id uuid NOT NULL REFERENCES football_brief.research_packets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'changes_requested')),
    reviewed_by text,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (workflow_run_id, source_output_id)
);

CREATE TABLE football_brief.step_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    source_output_id uuid NOT NULL,
    packet_id uuid NOT NULL REFERENCES football_brief.research_packets(id) ON DELETE RESTRICT,
    intake_id uuid NOT NULL REFERENCES football_brief.content_intakes(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    plan_hash char(64) NOT NULL,
    scenes jsonb NOT NULL DEFAULT '[]'::jsonb,
    requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
    notes jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, source_output_id, plan_hash)
);

COMMIT;
