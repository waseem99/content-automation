-- Football Brief Phase 1: workflow, audit, human review, cost, and render foundation
-- Depends on migrations/0001_phase0_asset_rights.sql
-- Target database: PostgreSQL 15+

BEGIN;

CREATE TABLE football_brief.content_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    working_title text NOT NULL,
    lifecycle_status text NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft', 'active', 'blocked', 'cancelled', 'published', 'archived'
    )),
    primary_platform text,
    content_format text,
    created_by text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER content_items_touch_updated_at
BEFORE UPDATE ON football_brief.content_items
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.workflow_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content_item_id uuid NOT NULL REFERENCES football_brief.content_items(id) ON DELETE RESTRICT,
    workflow_name text NOT NULL,
    workflow_version text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN (
        'active', 'blocked', 'failed', 'cancelled', 'archived', 'completed'
    )),
    current_stage text,
    input_hash char(64) NOT NULL,
    approved_budget_usd numeric(12, 4) CHECK (
        approved_budget_usd IS NULL OR approved_budget_usd >= 0
    ),
    actual_cost_usd numeric(12, 4) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    failure_reason text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (content_item_id, workflow_name, workflow_version, input_hash)
);

CREATE INDEX workflow_runs_status_stage_idx
    ON football_brief.workflow_runs (status, current_stage);
CREATE INDEX workflow_runs_content_idx
    ON football_brief.workflow_runs (content_item_id, created_at DESC);

CREATE TRIGGER workflow_runs_touch_updated_at
BEFORE UPDATE ON football_brief.workflow_runs
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.stage_executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_name text NOT NULL,
    stage_version text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'needs_revision',
        'awaiting_human', 'rejected', 'skipped', 'superseded'
    )),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    idempotency_key text NOT NULL,
    input_hash char(64) NOT NULL,
    output_hash char(64),
    model_or_tool text,
    prompt_version text,
    timeout_seconds integer CHECK (timeout_seconds IS NULL OR timeout_seconds > 0),
    estimated_cost_usd numeric(12, 4) CHECK (
        estimated_cost_usd IS NULL OR estimated_cost_usd >= 0
    ),
    actual_cost_usd numeric(12, 4) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    started_at timestamptz,
    completed_at timestamptz,
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    output jsonb,
    failure_reason text,
    operator text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, stage_name, attempt),
    UNIQUE (idempotency_key)
);

CREATE INDEX stage_executions_run_status_idx
    ON football_brief.stage_executions (workflow_run_id, status);
CREATE INDEX stage_executions_stage_idx
    ON football_brief.stage_executions (stage_name, created_at DESC);

CREATE TABLE football_brief.workflow_events (
    id bigserial PRIMARY KEY,
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    event_type text NOT NULL,
    from_status text,
    to_status text,
    actor text,
    reason text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX workflow_events_run_idx
    ON football_brief.workflow_events (workflow_run_id, created_at);

CREATE TABLE football_brief.human_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    review_type text NOT NULL,
    decision text NOT NULL CHECK (decision IN (
        'pass', 'pass_with_disclosure', 'human_review_required', 'block',
        'approved', 'rejected', 'changes_requested'
    )),
    reviewer text NOT NULL,
    rationale text NOT NULL,
    checklist jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX human_reviews_run_idx
    ON football_brief.human_reviews (workflow_run_id, created_at DESC);

CREATE TABLE football_brief.provider_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_execution_id uuid NOT NULL REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    operation text NOT NULL,
    provider_request_id text,
    idempotency_key text NOT NULL,
    status text NOT NULL CHECK (status IN (
        'pending', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    request_fingerprint char(64) NOT NULL,
    response_fingerprint char(64),
    units numeric(16, 6) CHECK (units IS NULL OR units >= 0),
    unit_name text,
    cost_usd numeric(12, 4) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    error_code text,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (provider, idempotency_key)
);

CREATE INDEX provider_calls_stage_idx
    ON football_brief.provider_calls (stage_execution_id, started_at);

CREATE TABLE football_brief.cost_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    provider_call_id uuid REFERENCES football_brief.provider_calls(id) ON DELETE RESTRICT,
    category text NOT NULL,
    amount_usd numeric(12, 4) NOT NULL CHECK (amount_usd >= 0),
    quantity numeric(16, 6) CHECK (quantity IS NULL OR quantity >= 0),
    unit_name text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX cost_entries_run_idx
    ON football_brief.cost_entries (workflow_run_id, created_at);

CREATE TABLE football_brief.prompt_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_name text NOT NULL,
    version text NOT NULL,
    content_hash char(64) NOT NULL,
    storage_uri text NOT NULL,
    active boolean NOT NULL DEFAULT false,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (prompt_name, version),
    UNIQUE (prompt_name, content_hash)
);

CREATE TABLE football_brief.policy_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name text NOT NULL,
    version text NOT NULL,
    content_hash char(64) NOT NULL,
    storage_uri text NOT NULL,
    effective_from timestamptz NOT NULL,
    active boolean NOT NULL DEFAULT false,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_name, version)
);

CREATE TABLE football_brief.brand_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name text NOT NULL,
    version text NOT NULL,
    content_hash char(64) NOT NULL,
    storage_uri text NOT NULL,
    active boolean NOT NULL DEFAULT false,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_name, version)
);

CREATE TABLE football_brief.render_manifests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content_item_id uuid NOT NULL REFERENCES football_brief.content_items(id) ON DELETE RESTRICT,
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    manifest_version integer NOT NULL DEFAULT 1 CHECK (manifest_version >= 1),
    mode text NOT NULL CHECK (mode IN ('preview', 'publish')),
    platform text NOT NULL,
    aspect_ratio text NOT NULL,
    script_version text,
    storyboard_version text,
    brand_version text NOT NULL,
    policy_version text NOT NULL,
    ai_disclosure_required boolean NOT NULL DEFAULT false,
    ai_disclosure_reason text,
    manifest jsonb NOT NULL,
    manifest_hash char(64) NOT NULL UNIQUE,
    approved_by text,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT publish_manifest_requires_approval CHECK (
        mode <> 'publish' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

CREATE TABLE football_brief.render_manifest_assets (
    render_manifest_id uuid NOT NULL REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    asset_rights_id uuid NOT NULL REFERENCES football_brief.asset_rights(id) ON DELETE RESTRICT,
    asset_sha256 char(64) NOT NULL,
    asset_role text NOT NULL,
    sequence_number integer NOT NULL DEFAULT 0 CHECK (sequence_number >= 0),
    PRIMARY KEY (render_manifest_id, asset_id, asset_role, sequence_number)
);

CREATE INDEX render_manifest_assets_asset_idx
    ON football_brief.render_manifest_assets (asset_id);

CREATE TABLE football_brief.render_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    render_manifest_id uuid NOT NULL REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    started_at timestamptz,
    completed_at timestamptz,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX render_jobs_manifest_idx
    ON football_brief.render_jobs (render_manifest_id, created_at DESC);

CREATE TABLE football_brief.quality_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    render_job_id uuid NOT NULL REFERENCES football_brief.render_jobs(id) ON DELETE RESTRICT,
    overall_status text NOT NULL CHECK (overall_status IN (
        'pass', 'pass_with_disclosure', 'human_review_required', 'block'
    )),
    checks jsonb NOT NULL DEFAULT '{}'::jsonb,
    blocking_failures jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX quality_reports_job_idx
    ON football_brief.quality_reports (render_job_id, created_at DESC);

CREATE TABLE football_brief.operator_actions (
    id bigserial PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    reason text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX operator_actions_entity_idx
    ON football_brief.operator_actions (entity_type, entity_id, created_at);

COMMENT ON TABLE football_brief.stage_executions IS
    'Immutable-attempt execution records. A retry creates a new attempt rather than overwriting prior evidence.';
COMMENT ON TABLE football_brief.render_manifests IS
    'Immutable approved instructions for a deterministic preview or publish render.';
COMMENT ON TABLE football_brief.provider_calls IS
    'Provider-level idempotency and cost audit. Secrets and raw sensitive payloads must not be stored.';

COMMIT;
