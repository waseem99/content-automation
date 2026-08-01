-- P127 retained acceptance evidence for the 1,000-item automatic pre-generation gate.

BEGIN;

CREATE TABLE football_brief.autopilot_acceptance_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    acceptance_key text NOT NULL UNIQUE
        CHECK (acceptance_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    campaign_id uuid REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    campaign_version_id uuid REFERENCES football_brief.production_campaign_versions(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed')),
    requested_items integer NOT NULL CHECK (requested_items BETWEEN 1 AND 20000),
    expected_ready integer NOT NULL CHECK (expected_ready BETWEEN 0 AND requested_items),
    expected_hard_blocks integer NOT NULL CHECK (expected_hard_blocks BETWEEN 0 AND requested_items),
    ready_items integer NOT NULL DEFAULT 0 CHECK (ready_items >= 0),
    hard_block_items integer NOT NULL DEFAULT 0 CHECK (hard_block_items >= 0),
    human_exception_items integer NOT NULL DEFAULT 0 CHECK (human_exception_items >= 0),
    auto_correction_items integer NOT NULL DEFAULT 0 CHECK (auto_correction_items >= 0),
    automation_rate numeric(8,6) NOT NULL DEFAULT 0 CHECK (automation_rate BETWEEN 0 AND 1),
    grouped_source_blocks integer NOT NULL DEFAULT 0 CHECK (grouped_source_blocks >= 0),
    individual_page_approvals integer NOT NULL DEFAULT 0 CHECK (individual_page_approvals >= 0),
    content_families integer NOT NULL DEFAULT 0 CHECK (content_families >= 0),
    script_documents integer NOT NULL DEFAULT 0 CHECK (script_documents >= 0),
    reproducible_ready_decisions integer NOT NULL DEFAULT 0 CHECK (reproducible_ready_decisions >= 0),
    timings_ms jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(timings_ms)='object'),
    counters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(counters)='object'),
    environment jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(environment)='object'),
    error jsonb CHECK (error IS NULL OR jsonb_typeof(error)='object'),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='running' OR completed_at IS NOT NULL),
    CHECK (ready_items + hard_block_items + human_exception_items <= requested_items),
    CHECK (status<>'passed' OR (
        ready_items >= expected_ready
        AND hard_block_items = expected_hard_blocks
        AND human_exception_items = 0
        AND automation_rate >= 0.95
        AND individual_page_approvals = 0
        AND reproducible_ready_decisions >= expected_ready
    ))
);

CREATE INDEX autopilot_acceptance_runs_created_idx
ON football_brief.autopilot_acceptance_runs(created_at DESC,id DESC);

COMMENT ON TABLE football_brief.autopilot_acceptance_runs IS
    'Retained measured evidence for automatic 1,000-item progression and grouped hard blockers; no final rendering or publishing.';

COMMIT;
