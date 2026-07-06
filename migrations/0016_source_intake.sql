-- Football Brief P2: source intake foundation
-- Depends on migrations/0001 through 0015

BEGIN;

CREATE TABLE football_brief.content_intakes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    topic text,
    angle text,
    status text NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'rejected')),
    canonical_input_hash char(64) NOT NULL,
    football_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    rejection_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT content_intakes_topic_or_source_hash CHECK (
        nullif(btrim(coalesce(topic, '')), '') IS NOT NULL
        OR canonical_input_hash IS NOT NULL
    ),
    UNIQUE (workflow_run_id, canonical_input_hash)
);

CREATE INDEX content_intakes_workflow_created_idx
    ON football_brief.content_intakes (workflow_run_id, created_at DESC);
CREATE INDEX content_intakes_status_idx
    ON football_brief.content_intakes (status, created_at DESC);

CREATE TRIGGER content_intakes_touch_updated_at
BEFORE UPDATE ON football_brief.content_intakes
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.content_intake_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id uuid NOT NULL REFERENCES football_brief.content_intakes(id) ON DELETE RESTRICT,
    source_url text NOT NULL,
    normalized_url text NOT NULL,
    source_type text NOT NULL DEFAULT 'url' CHECK (source_type IN ('url')),
    source_hash char(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (intake_id, source_hash)
);

CREATE INDEX content_intake_sources_intake_idx
    ON football_brief.content_intake_sources (intake_id, created_at);
CREATE INDEX content_intake_sources_hash_idx
    ON football_brief.content_intake_sources (source_hash);

COMMIT;
