-- P120 automatic pre-generation orchestration, grouped exceptions and storage reconciliation.
-- Stops at ready_for_final_video_generation. No paid rendering or publishing.

BEGIN;

CREATE TABLE football_brief.pre_generation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_item_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    autopilot_policy_id uuid NOT NULL
        REFERENCES football_brief.pre_generation_autopilot_policies(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued','running','waiting','human_exception','hard_block','ready','failed','cancelled'
    )),
    current_stage text NOT NULL DEFAULT 'content_expansion' CHECK (current_stage IN (
        'content_expansion','script_generation','script_checks','script_approval',
        'narration_plan','scene_plan','caption_package','final_generation_package','complete'
    )),
    stage_attempt integer NOT NULL DEFAULT 0 CHECK (stage_attempt >= 0),
    correction_count integer NOT NULL DEFAULT 0 CHECK (correction_count >= 0),
    score numeric(5,2) CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    lease_owner text,
    lease_token uuid,
    lease_expires_at timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    portfolio_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    script_document_id uuid REFERENCES football_brief.script_documents(id) ON DELETE RESTRICT,
    package_id uuid REFERENCES football_brief.pre_generation_packages(id) ON DELETE RESTRICT,
    last_error_code text,
    last_error_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT pre_generation_run_lease_valid CHECK (
        (lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)
        OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
    )
);

CREATE INDEX pre_generation_runs_claim_idx
ON football_brief.pre_generation_runs
(status, next_attempt_at, lease_expires_at, updated_at)
WHERE status IN ('queued','running','waiting');

CREATE INDEX pre_generation_runs_campaign_idx
ON football_brief.pre_generation_runs(campaign_item_id, current_stage, status);

CREATE TABLE football_brief.pre_generation_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES football_brief.pre_generation_runs(id) ON DELETE RESTRICT,
    stage text NOT NULL,
    check_key text NOT NULL CHECK (length(btrim(check_key)) BETWEEN 2 AND 120),
    rule_version text NOT NULL CHECK (length(btrim(rule_version)) BETWEEN 1 AND 120),
    status text NOT NULL CHECK (status IN ('passed','corrected','warning','failed','blocked')),
    score numeric(5,2) CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, stage, check_key, rule_version)
);

CREATE INDEX pre_generation_checks_run_idx
ON football_brief.pre_generation_checks(run_id, stage, status, created_at);

CREATE TABLE football_brief.pre_generation_exceptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES football_brief.pre_generation_runs(id) ON DELETE RESTRICT,
    campaign_item_id uuid NOT NULL
        REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    exception_code text NOT NULL CHECK (length(btrim(exception_code)) BETWEEN 2 AND 120),
    category text NOT NULL CHECK (category IN (
        'source','duplication','duration','brand','narration','continuity',
        'rights','safety','territory','budget','storage','system','structural'
    )),
    severity text NOT NULL CHECK (severity IN ('warning','human_exception','hard_block')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','waived','superseded')),
    rule_version text NOT NULL,
    fingerprint char(64) NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    resolution jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolved_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    UNIQUE (run_id, exception_code, fingerprint)
);

CREATE INDEX pre_generation_exceptions_group_idx
ON football_brief.pre_generation_exceptions(status, severity, category, exception_code, rule_version);

CREATE TABLE football_brief.production_campaign_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    action_type text NOT NULL CHECK (action_type IN (
        'start_autopilot','retry','pause','resume','hold','release_hold','resolve_exception'
    )),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','partial','failed')),
    selection jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_count integer NOT NULL DEFAULT 0 CHECK (requested_count >= 0),
    succeeded_count integer NOT NULL DEFAULT 0 CHECK (succeeded_count >= 0),
    failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz
);

CREATE INDEX production_campaign_actions_status_idx
ON football_brief.production_campaign_actions(campaign_id, status, created_at DESC);

ALTER TABLE football_brief.asset_storage_locations
    ADD COLUMN last_checked_at timestamptz,
    ADD COLUMN last_error_code text,
    ADD COLUMN reconciliation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE football_brief.asset_storage_reconciliation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text CHECK (provider IS NULL OR provider IN ('local','google_drive')),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','partial','failed')),
    checked_count integer NOT NULL DEFAULT 0 CHECK (checked_count >= 0),
    available_count integer NOT NULL DEFAULT 0 CHECK (available_count >= 0),
    missing_count integer NOT NULL DEFAULT 0 CHECK (missing_count >= 0),
    mismatch_count integer NOT NULL DEFAULT 0 CHECK (mismatch_count >= 0),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX asset_storage_reconciliation_runs_idx
ON football_brief.asset_storage_reconciliation_runs(created_at DESC, status);

-- Activated campaign items receive exactly one durable autopilot run.
INSERT INTO football_brief.pre_generation_runs(campaign_item_id, autopilot_policy_id, status)
SELECT item.id, version.autopilot_policy_id, 'queued'
FROM football_brief.production_campaign_items item
JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
WHERE item.state='activated'
ON CONFLICT (campaign_item_id) DO NOTHING;

COMMENT ON TABLE football_brief.pre_generation_runs IS
    'Durable automatic progression from campaign activation to immutable final-generation package.';
COMMENT ON TABLE football_brief.pre_generation_exceptions IS
    'Grouped operator attention only; routine passed items never require individual approval.';

COMMIT;
