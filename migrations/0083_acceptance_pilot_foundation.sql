-- Bounded Rawr Nation / Animal X production acceptance pilot.
-- This schema records evidence and sign-off only. It does not enable live delivery adapters.

BEGIN;

CREATE TABLE football_brief.acceptance_pilots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_key text NOT NULL CHECK (pilot_key ~ '^[a-z0-9][a-z0-9._-]{7,119}$'),
    version integer NOT NULL CHECK (version>=1),
    parent_pilot_id uuid REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft','running','blocked','accepted','retired')
    ),
    scope jsonb NOT NULL CHECK (jsonb_typeof(scope)='object'),
    acceptance_policy jsonb NOT NULL CHECK (jsonb_typeof(acceptance_policy)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    accepted_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    accepted_at timestamptz,
    retired_at timestamptz,
    UNIQUE (pilot_key,version),
    CHECK (version=1 OR parent_pilot_id IS NOT NULL),
    CHECK (version<>1 OR parent_pilot_id IS NULL),
    CHECK (status<>'running' OR started_at IS NOT NULL),
    CHECK (status<>'accepted' OR (accepted_by IS NOT NULL AND accepted_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX acceptance_one_active_pilot_idx
ON football_brief.acceptance_pilots(pilot_key)
WHERE status IN ('draft','running','blocked');

CREATE TABLE football_brief.acceptance_pilot_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_id uuid NOT NULL REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version>=1),
    production_mode text NOT NULL CHECK (production_mode IN ('local_only','managed_render')),
    required_revision_stages text[] NOT NULL DEFAULT ARRAY['script','narration','visual']::text[] CHECK (
        required_revision_stages <@ ARRAY['script','narration','visual']::text[]
        AND cardinality(required_revision_stages)>=1
    ),
    staging_delivery_request_id uuid REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    live_delivery_evidence_required boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ready','blocked','passed')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_id,portfolio_content_id,content_version),
    UNIQUE (pilot_id,brand_id,portfolio_content_id),
    CHECK (production_mode<>'managed_render' OR live_delivery_evidence_required IN (true,false))
);

CREATE INDEX acceptance_pilot_items_brand_idx
ON football_brief.acceptance_pilot_items(pilot_id,brand_id,status);

CREATE TABLE football_brief.acceptance_pilot_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_item_id uuid NOT NULL REFERENCES football_brief.acceptance_pilot_items(id) ON DELETE RESTRICT,
    category text NOT NULL CHECK (category IN (
        'brand_profile','narration_preset','role_assignment','concept_approval','source_evidence',
        'script_approval','script_revision','narration_approval','narration_revision',
        'visual_approval','visual_revision','routing_explanation','spend_approval',
        'renderer_lineage','artifact_lineage','final_qa','release_manifest',
        'publisher_decision','staging_delivery','analytics_observation','production_economics',
        'backup_restore','worker_restart','runbook_validation'
    )),
    passed boolean NOT NULL,
    subject_type text NOT NULL CHECK (length(btrim(subject_type)) BETWEEN 2 AND 120),
    subject_id text NOT NULL CHECK (length(btrim(subject_id)) BETWEEN 1 AND 240),
    subject_version text,
    details jsonb NOT NULL CHECK (jsonb_typeof(details)='object'),
    details_digest char(64) NOT NULL CHECK (details_digest ~ '^[0-9a-f]{64}$'),
    observed_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    observed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_item_id,category,subject_type,subject_id,details_digest)
);

CREATE INDEX acceptance_pilot_evidence_item_idx
ON football_brief.acceptance_pilot_evidence(pilot_item_id,category,passed,observed_at DESC);

CREATE TABLE football_brief.acceptance_pilot_defects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_id uuid NOT NULL REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    pilot_item_id uuid REFERENCES football_brief.acceptance_pilot_items(id) ON DELETE RESTRICT,
    defect_key text NOT NULL CHECK (defect_key ~ '^[a-z0-9][a-z0-9._-]{4,159}$'),
    severity text NOT NULL CHECK (severity IN ('minor','major','critical')),
    summary text NOT NULL CHECK (length(btrim(summary)) BETWEEN 3 AND 1000),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','waived')),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence)='object'),
    opened_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    opened_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolution text,
    UNIQUE (pilot_id,defect_key),
    CHECK (status='open' OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL AND resolution IS NOT NULL)),
    CHECK (severity='minor' OR status<>'waived')
);

CREATE INDEX acceptance_pilot_defects_open_idx
ON football_brief.acceptance_pilot_defects(pilot_id,severity,status)
WHERE status='open';

CREATE TABLE football_brief.acceptance_pilot_signoffs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_id uuid NOT NULL REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    signoff_role text NOT NULL CHECK (signoff_role IN ('admin','reviewer','publisher')),
    decision text NOT NULL CHECK (decision IN ('approved','rejected')),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 2000),
    operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    evidence_snapshot jsonb NOT NULL CHECK (jsonb_typeof(evidence_snapshot)='object'),
    evidence_digest char(64) NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_id,signoff_role)
);

CREATE TABLE football_brief.acceptance_live_delivery_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_id uuid NOT NULL REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    pilot_item_id uuid NOT NULL REFERENCES football_brief.acceptance_pilot_items(id) ON DELETE RESTRICT,
    final_release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    platform text NOT NULL CHECK (length(btrim(platform)) BETWEEN 2 AND 80),
    platform_reference text NOT NULL CHECK (length(btrim(platform_reference)) BETWEEN 3 AND 500),
    result_status text NOT NULL CHECK (result_status IN ('submitted','published','failed','removed')),
    external_response_digest char(64) NOT NULL CHECK (external_response_digest ~ '^[0-9a-f]{64}$'),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    recorded_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_item_id,platform,platform_reference)
);

CREATE TABLE football_brief.acceptance_pilot_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_id uuid NOT NULL REFERENCES football_brief.acceptance_pilots(id) ON DELETE RESTRICT,
    pilot_item_id uuid REFERENCES football_brief.acceptance_pilot_items(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'pilot_created','pilot_started','item_added','evidence_recorded','item_evaluated',
        'defect_opened','defect_resolved','signoff_recorded','live_delivery_evidence_recorded',
        'pilot_blocked','pilot_accepted','pilot_retired'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX acceptance_pilot_events_idx
ON football_brief.acceptance_pilot_events(pilot_id,created_at,id);

COMMENT ON TABLE football_brief.acceptance_live_delivery_evidence IS
    'Externally recorded live-delivery result after complete pilot sign-off. No live adapter or credential is enabled by P100.';

COMMIT;
