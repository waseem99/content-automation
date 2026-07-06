-- Football Brief P2: draft output foundation
-- Depends on migrations/0001 through 0018

BEGIN;

CREATE TABLE football_brief.draft_outputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    packet_id uuid NOT NULL REFERENCES football_brief.research_packets(id) ON DELETE RESTRICT,
    intake_id uuid NOT NULL REFERENCES football_brief.content_intakes(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    draft_version text NOT NULL DEFAULT '1',
    status text NOT NULL DEFAULT 'review_required' CHECK (status IN ('review_required', 'superseded')),
    draft_hash char(64) NOT NULL,
    title text NOT NULL,
    hook text NOT NULL,
    outline jsonb NOT NULL DEFAULT '[]'::jsonb,
    narration jsonb NOT NULL DEFAULT '[]'::jsonb,
    citation_map jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, packet_id, draft_hash)
);

CREATE INDEX draft_outputs_workflow_idx
    ON football_brief.draft_outputs (workflow_run_id, created_at DESC);
CREATE INDEX draft_outputs_packet_idx
    ON football_brief.draft_outputs (packet_id, created_at DESC);
CREATE INDEX draft_outputs_stage_idx
    ON football_brief.draft_outputs (stage_execution_id)
    WHERE stage_execution_id IS NOT NULL;

COMMIT;
