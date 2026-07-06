-- Football Brief P2: packet persistence foundation
-- Depends on migrations/0001 through 0016

BEGIN;

CREATE TABLE football_brief.research_packets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    intake_id uuid NOT NULL REFERENCES football_brief.content_intakes(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    packet_version text NOT NULL DEFAULT '1',
    status text NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'superseded')),
    packet_hash char(64) NOT NULL,
    source_metadata jsonb NOT NULL DEFAULT '[]'::jsonb,
    extracted_claims jsonb NOT NULL DEFAULT '[]'::jsonb,
    quote_boundaries jsonb NOT NULL DEFAULT '[]'::jsonb,
    entities jsonb NOT NULL DEFAULT '{}'::jsonb,
    freshness jsonb NOT NULL DEFAULT '{}'::jsonb,
    citations jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence_notes text,
    provider_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, intake_id, packet_hash)
);

CREATE INDEX research_packets_workflow_idx
    ON football_brief.research_packets (workflow_run_id, created_at DESC);
CREATE INDEX research_packets_intake_idx
    ON football_brief.research_packets (intake_id, created_at DESC);
CREATE INDEX research_packets_stage_idx
    ON football_brief.research_packets (stage_execution_id)
    WHERE stage_execution_id IS NOT NULL;

COMMIT;
