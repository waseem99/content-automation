-- Versioned external renderer catalogue and append-only preflight evidence.
-- P93 does not enable paid provider submission. CI and execution use simulated zero-fee adapters only.

BEGIN;

CREATE TABLE football_brief.renderer_catalogue_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key text NOT NULL CHECK (provider_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    provider_display_name text NOT NULL CHECK (length(btrim(provider_display_name)) BETWEEN 2 AND 200),
    model_key text NOT NULL CHECK (model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$'),
    model_display_name text NOT NULL CHECK (length(btrim(model_display_name)) BETWEEN 2 AND 200),
    operation text NOT NULL CHECK (operation IN (
        'text_to_video','image_to_video','video_to_video','lip_sync','video_edit'
    )),
    version integer NOT NULL CHECK (version >= 1),
    parent_entry_id uuid REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    adapter_kind text NOT NULL CHECK (adapter_kind IN ('simulated','http_api','managed_sdk')),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    health_status text NOT NULL DEFAULT 'unknown' CHECK (
        health_status IN ('unknown','healthy','degraded','unavailable')
    ),
    supported_formats text[] NOT NULL DEFAULT ARRAY[]::text[],
    min_duration_seconds numeric(10,3) NOT NULL CHECK (min_duration_seconds > 0),
    max_duration_seconds numeric(10,3) NOT NULL CHECK (max_duration_seconds >= min_duration_seconds),
    duration_step_seconds numeric(10,3) CHECK (duration_step_seconds IS NULL OR duration_step_seconds > 0),
    supported_resolutions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(supported_resolutions)='array'),
    capabilities jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(capabilities)='object'),
    expected_latency_seconds jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(expected_latency_seconds)='object'),
    pricing jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(pricing)='object'),
    pricing_currency char(3) NOT NULL DEFAULT 'USD' CHECK (pricing_currency ~ '^[A-Z]{3}$'),
    quality_rating numeric(5,2) NOT NULL DEFAULT 0 CHECK (quality_rating BETWEEN 0 AND 100),
    commercial_use_allowed boolean NOT NULL DEFAULT false,
    usage_terms_url text,
    usage_evidence_digest char(64) NOT NULL CHECK (usage_evidence_digest ~ '^[0-9a-f]{64}$'),
    usage_evidence_recorded_at timestamptz NOT NULL,
    data_handling jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(data_handling)='object'),
    notes text,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (provider_key, model_key, operation, version),
    UNIQUE (id, provider_key, model_key, operation),
    CHECK (version = 1 OR parent_entry_id IS NOT NULL),
    CHECK (version <> 1 OR parent_entry_id IS NULL),
    CHECK (status <> 'active' OR (activated_at IS NOT NULL AND activated_by IS NOT NULL)),
    CHECK (status <> 'retired' OR (retired_at IS NOT NULL AND retired_by IS NOT NULL)),
    CHECK (adapter_kind <> 'simulated' OR provider_key = 'simulated')
);

CREATE UNIQUE INDEX renderer_catalogue_one_active_idx
ON football_brief.renderer_catalogue_entries (provider_key, model_key, operation)
WHERE status='active';

CREATE INDEX renderer_catalogue_lookup_idx
ON football_brief.renderer_catalogue_entries (status, operation, provider_key, model_key);

CREATE TRIGGER renderer_catalogue_touch_updated_at
BEFORE UPDATE ON football_brief.renderer_catalogue_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.renderer_health_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    renderer_catalogue_entry_id uuid NOT NULL
        REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('healthy','degraded','unavailable')),
    latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
    checked_by text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    observed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX renderer_health_entry_idx
ON football_brief.renderer_health_observations (renderer_catalogue_entry_id, observed_at DESC);

CREATE TABLE football_brief.renderer_preflight_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version >= 1),
    renderer_catalogue_entry_id uuid
        REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    operation text NOT NULL CHECK (operation IN (
        'text_to_video','image_to_video','video_to_video','lip_sync','video_edit'
    )),
    request_fingerprint char(64) NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    request_payload jsonb NOT NULL CHECK (jsonb_typeof(request_payload)='object'),
    accepted boolean NOT NULL,
    rejection_reasons jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rejection_reasons)='array'),
    estimated_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    pricing_currency char(3) NOT NULL DEFAULT 'USD' CHECK (pricing_currency ~ '^[A-Z]{3}$'),
    expected_seconds integer CHECK (expected_seconds IS NULL OR expected_seconds >= 0),
    external_fee_possible boolean NOT NULL DEFAULT false,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_content_id, content_version, request_fingerprint),
    CHECK (accepted OR jsonb_array_length(rejection_reasons) > 0)
);

CREATE INDEX renderer_preflight_content_idx
ON football_brief.renderer_preflight_records (portfolio_content_id, content_version, created_at DESC);

CREATE TABLE football_brief.renderer_job_bindings (
    generation_job_id uuid PRIMARY KEY REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    renderer_preflight_id uuid NOT NULL UNIQUE REFERENCES football_brief.renderer_preflight_records(id) ON DELETE RESTRICT,
    renderer_catalogue_entry_id uuid NOT NULL REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    request_fingerprint char(64) NOT NULL,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE football_brief.renderer_catalogue_entries IS
    'Versioned renderer capabilities, commercial-use evidence, health, latency, quality, and pricing. Active versions are immutable except retirement.';
COMMENT ON TABLE football_brief.renderer_preflight_records IS
    'Append-only accepted or rejected renderer request evidence created before any job submission.';
COMMENT ON TABLE football_brief.renderer_job_bindings IS
    'Exact binding from a generation job to the accepted catalogue version and preflight quote used.';

COMMIT;
