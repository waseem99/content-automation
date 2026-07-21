-- Versioned production renderer catalogue and simulated adapter attempt evidence.
-- P93 records external capabilities and prices but permits execution only for simulated entries.

BEGIN;

CREATE TABLE football_brief.production_renderer_catalogue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    renderer_key text NOT NULL CHECK (renderer_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
    version integer NOT NULL CHECK (version >= 1),
    parent_renderer_id uuid REFERENCES football_brief.production_renderer_catalogue(id) ON DELETE RESTRICT,
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 200),
    adapter_key text NOT NULL CHECK (length(btrim(adapter_key)) BETWEEN 2 AND 120),
    operation text NOT NULL CHECK (operation IN (
        'text_to_video','image_to_video','video_to_video','upscale'
    )),
    output_formats text[] NOT NULL CHECK (cardinality(output_formats) >= 1),
    min_duration_seconds numeric(12,3) NOT NULL DEFAULT 0 CHECK (min_duration_seconds >= 0),
    max_duration_seconds numeric(12,3) NOT NULL CHECK (
        max_duration_seconds > 0 AND max_duration_seconds >= min_duration_seconds
    ),
    max_width integer NOT NULL CHECK (max_width BETWEEN 64 AND 16384),
    max_height integer NOT NULL CHECK (max_height BETWEEN 64 AND 16384),
    capabilities text[] NOT NULL DEFAULT '{}',
    expected_seconds_base numeric(14,3) NOT NULL DEFAULT 0 CHECK (expected_seconds_base >= 0),
    expected_seconds_per_second numeric(14,3) NOT NULL DEFAULT 0 CHECK (expected_seconds_per_second >= 0),
    base_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (base_cost_usd >= 0),
    cost_per_second_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (cost_per_second_usd >= 0),
    usage_evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(usage_evidence)='object'),
    health text NOT NULL DEFAULT 'unknown' CHECK (health IN (
        'unknown','healthy','degraded','unavailable'
    )),
    quality_rating numeric(3,2) NOT NULL DEFAULT 0 CHECK (quality_rating BETWEEN 0 AND 5),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    simulated boolean NOT NULL DEFAULT false,
    execution_enabled boolean NOT NULL DEFAULT false,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (renderer_key, version),
    CONSTRAINT production_renderer_parent_not_self CHECK (parent_renderer_id IS NULL OR parent_renderer_id <> id),
    CONSTRAINT production_renderer_simulated_adapter CHECK (
        NOT simulated OR adapter_key='simulated'
    ),
    CONSTRAINT production_renderer_p93_execution_boundary CHECK (
        NOT execution_enabled OR simulated
    ),
    CONSTRAINT production_renderer_activation_consistent CHECK (
        (status='draft' AND activated_at IS NULL AND activated_by IS NULL AND retired_at IS NULL AND retired_by IS NULL)
        OR (status='active' AND activated_at IS NOT NULL AND activated_by IS NOT NULL AND retired_at IS NULL AND retired_by IS NULL)
        OR (status='retired' AND retired_at IS NOT NULL AND retired_by IS NOT NULL)
    )
);

CREATE UNIQUE INDEX production_renderer_one_active_key
ON football_brief.production_renderer_catalogue(renderer_key)
WHERE status='active';

CREATE INDEX production_renderer_resolution_idx
ON football_brief.production_renderer_catalogue
    (status, operation, health, base_cost_usd, quality_rating DESC);

CREATE TRIGGER production_renderer_catalogue_touch_updated_at
BEFORE UPDATE ON football_brief.production_renderer_catalogue
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.production_renderer_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    renderer_id uuid NOT NULL
        REFERENCES football_brief.production_renderer_catalogue(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'created','activated','retired','repriced','health_updated'
    )),
    actor_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX production_renderer_events_renderer_idx
ON football_brief.production_renderer_events(renderer_id, created_at, id);

CREATE TABLE football_brief.production_renderer_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    renderer_id uuid NOT NULL
        REFERENCES football_brief.production_renderer_catalogue(id) ON DELETE RESTRICT,
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) BETWEEN 8 AND 240),
    input_fingerprint char(64) NOT NULL,
    request_spec jsonb NOT NULL CHECK (jsonb_typeof(request_spec)='object'),
    input_payload jsonb NOT NULL CHECK (jsonb_typeof(input_payload)='object'),
    catalogue_snapshot jsonb NOT NULL CHECK (jsonb_typeof(catalogue_snapshot)='object'),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','succeeded','failed')),
    estimated_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    expected_seconds numeric(14,3) NOT NULL DEFAULT 0 CHECK (expected_seconds >= 0),
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    provider_request_id text,
    output_payload jsonb,
    error_code text,
    error_message text,
    submitted_by text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CONSTRAINT production_renderer_attempt_terminal_consistent CHECK (
        (status='running' AND finished_at IS NULL AND output_payload IS NULL AND error_code IS NULL)
        OR (status='succeeded' AND finished_at IS NOT NULL AND output_payload IS NOT NULL
            AND provider_request_id IS NOT NULL AND error_code IS NULL)
        OR (status='failed' AND finished_at IS NOT NULL AND error_code IS NOT NULL
            AND error_message IS NOT NULL AND output_payload IS NULL)
    )
);

CREATE INDEX production_renderer_attempts_renderer_idx
ON football_brief.production_renderer_attempts(renderer_id, submitted_at DESC, id);

COMMENT ON TABLE football_brief.production_renderer_catalogue IS
    'Versioned, provider-neutral production renderer capability and pricing records. P93 executes simulated adapters only.';
COMMENT ON TABLE football_brief.production_renderer_attempts IS
    'Immutable exact-input and catalogue snapshots for simulated renderer submissions, including failures.';

COMMIT;
