-- Football Brief P2: review prerequisite foundation
-- Depends on migrations/0001 through 0017

BEGIN;

CREATE TABLE football_brief.review_prerequisites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    packet_id uuid NOT NULL REFERENCES football_brief.research_packets(id) ON DELETE RESTRICT,
    intake_id uuid NOT NULL REFERENCES football_brief.content_intakes(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'changes_requested', 'rejected')),
    requested_by text NOT NULL,
    reviewed_by text,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, packet_id)
);

CREATE INDEX review_prerequisites_workflow_status_idx
    ON football_brief.review_prerequisites (workflow_run_id, status, created_at DESC);
CREATE INDEX review_prerequisites_packet_idx
    ON football_brief.review_prerequisites (packet_id);

CREATE TRIGGER review_prerequisites_touch_updated_at
BEFORE UPDATE ON football_brief.review_prerequisites
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

COMMIT;
