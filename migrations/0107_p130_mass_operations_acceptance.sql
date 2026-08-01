-- P130 durable campaign selections, background mass-operation jobs, exact item
-- results, optimistic inline edit evidence and retained acceptance results.

BEGIN;

CREATE TABLE football_brief.campaign_selection_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    snapshot_key text NOT NULL UNIQUE CHECK (snapshot_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','consumed','superseded')),
    filters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(filters)='object'),
    item_count integer NOT NULL CHECK (item_count BETWEEN 1 AND 20000),
    snapshot_sha256 char(64) NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    consumed_at timestamptz,
    CHECK (status<>'consumed' OR consumed_at IS NOT NULL)
);

CREATE TABLE football_brief.campaign_selection_members (
    snapshot_id uuid NOT NULL REFERENCES football_brief.campaign_selection_snapshots(id) ON DELETE RESTRICT,
    campaign_item_id uuid NOT NULL REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal>=1),
    item_updated_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_id,campaign_item_id),
    UNIQUE (snapshot_id,ordinal)
);

CREATE INDEX campaign_selection_members_item_idx
ON football_brief.campaign_selection_members(campaign_item_id,snapshot_id);

CREATE TABLE football_brief.campaign_mass_operation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES football_brief.campaign_selection_snapshots(id) ON DELETE RESTRICT,
    action_type text NOT NULL CHECK (action_type IN ('retry')),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','partial','failed')),
    requested_count integer NOT NULL CHECK (requested_count BETWEEN 1 AND 20000),
    succeeded_count integer NOT NULL DEFAULT 0 CHECK (succeeded_count>=0),
    skipped_count integer NOT NULL DEFAULT 0 CHECK (skipped_count>=0),
    failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count>=0),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    result jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(result)='object'),
    CHECK (status='queued' OR started_at IS NOT NULL),
    CHECK (status IN ('queued','running') OR completed_at IS NOT NULL),
    CHECK (succeeded_count+skipped_count+failed_count<=requested_count)
);

CREATE INDEX campaign_mass_operation_jobs_claim_idx
ON football_brief.campaign_mass_operation_jobs(status,created_at,id)
WHERE status='queued';

CREATE TABLE football_brief.campaign_mass_operation_item_results (
    job_id uuid NOT NULL REFERENCES football_brief.campaign_mass_operation_jobs(id) ON DELETE RESTRICT,
    campaign_item_id uuid NOT NULL REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    outcome text NOT NULL CHECK (outcome IN ('succeeded','skipped','failed')),
    before_state jsonb NOT NULL CHECK (jsonb_typeof(before_state)='object'),
    after_state jsonb NOT NULL CHECK (jsonb_typeof(after_state)='object'),
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id,campaign_item_id),
    CHECK (outcome<>'failed' OR error_code IS NOT NULL)
);

CREATE TABLE football_brief.campaign_inline_edit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_item_id uuid NOT NULL REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    expected_updated_at timestamptz NOT NULL,
    before_state jsonb NOT NULL CHECK (jsonb_typeof(before_state)='object'),
    after_state jsonb NOT NULL CHECK (jsonb_typeof(after_state)='object'),
    edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE football_brief.mass_operations_acceptance_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    acceptance_key text NOT NULL UNIQUE CHECK (acceptance_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed')),
    requested_items integer NOT NULL CHECK (requested_items BETWEEN 1000 AND 20000),
    snapshot_items integer NOT NULL DEFAULT 0 CHECK (snapshot_items>=0),
    succeeded_items integer NOT NULL DEFAULT 0 CHECK (succeeded_items>=0),
    skipped_items integer NOT NULL DEFAULT 0 CHECK (skipped_items>=0),
    failed_items integer NOT NULL DEFAULT 0 CHECK (failed_items>=0),
    exact_result_rows integer NOT NULL DEFAULT 0 CHECK (exact_result_rows>=0),
    grouped_exceptions_before integer NOT NULL DEFAULT 0 CHECK (grouped_exceptions_before>=0),
    grouped_exceptions_after integer NOT NULL DEFAULT 0 CHECK (grouped_exceptions_after>=0),
    optimistic_edit_passed boolean NOT NULL DEFAULT false,
    stale_edit_rejected boolean NOT NULL DEFAULT false,
    authorized_brand_action_passed boolean NOT NULL DEFAULT false,
    unauthorized_brand_action_rejected boolean NOT NULL DEFAULT false,
    timings_ms jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(timings_ms)='object'),
    counters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(counters)='object'),
    environment jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(environment)='object'),
    error jsonb CHECK (error IS NULL OR jsonb_typeof(error)='object'),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='running' OR completed_at IS NOT NULL),
    CHECK (status<>'passed' OR (
        snapshot_items=requested_items
        AND succeeded_items=requested_items
        AND skipped_items=0 AND failed_items=0
        AND exact_result_rows=requested_items
        AND grouped_exceptions_before=requested_items
        AND grouped_exceptions_after=0
        AND optimistic_edit_passed=true
        AND stale_edit_rejected=true
        AND authorized_brand_action_passed=true
        AND unauthorized_brand_action_rejected=true
    ))
);

CREATE OR REPLACE FUNCTION football_brief.protect_campaign_selection_members()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Campaign selection members and mass-operation results are immutable';
END;
$$;

CREATE TRIGGER campaign_selection_members_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_selection_members
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_selection_members();
CREATE TRIGGER campaign_mass_operation_item_results_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_mass_operation_item_results
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_selection_members();
CREATE TRIGGER campaign_inline_edit_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_inline_edit_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_selection_members();

COMMENT ON TABLE football_brief.campaign_mass_operation_jobs IS
    'Durable background database action over an immutable campaign selection snapshot.';

COMMIT;
