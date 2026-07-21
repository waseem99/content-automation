-- Versioned delivery targets, scheduled release requests, adapter attempts, and platform evidence.

BEGIN;

CREATE TABLE football_brief.platform_delivery_targets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_key text NOT NULL CHECK (target_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
    version integer NOT NULL CHECK (version>=1),
    parent_target_id uuid REFERENCES football_brief.platform_delivery_targets(id) ON DELETE RESTRICT,
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 200),
    platform text NOT NULL CHECK (length(btrim(platform)) BETWEEN 2 AND 80),
    environment text NOT NULL CHECK (environment IN ('test','staging','production')),
    primary_adapter_key text NOT NULL CHECK (length(btrim(primary_adapter_key)) BETWEEN 2 AND 120),
    fallback_adapter_key text CHECK (fallback_adapter_key IS NULL OR length(btrim(fallback_adapter_key)) BETWEEN 2 AND 120),
    supported_privacy text[] NOT NULL CHECK (
        cardinality(supported_privacy)>=1
        AND supported_privacy <@ ARRAY['private','unlisted','public']::text[]
    ),
    default_privacy text NOT NULL CHECK (default_privacy IN ('private','unlisted','public')),
    credential_secret_ref text,
    simulated boolean NOT NULL DEFAULT false,
    execution_enabled boolean NOT NULL DEFAULT false,
    requests_per_minute integer NOT NULL CHECK (requests_per_minute BETWEEN 1 AND 10000),
    requests_per_day integer NOT NULL CHECK (requests_per_day BETWEEN 1 AND 1000000),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','unavailable','retired')),
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (target_key,version),
    CHECK (version=1 OR parent_target_id IS NOT NULL),
    CHECK (version<>1 OR parent_target_id IS NULL),
    CHECK (default_privacy=ANY(supported_privacy)),
    CHECK (requests_per_day>=requests_per_minute),
    CHECK (NOT execution_enabled OR simulated),
    CHECK (credential_secret_ref IS NULL OR credential_secret_ref !~* '(password|secret|token|key)='),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX platform_delivery_one_active_target_idx
ON football_brief.platform_delivery_targets(target_key)
WHERE status='active';

CREATE TABLE football_brief.platform_delivery_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    final_release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES football_brief.platform_delivery_targets(id) ON DELETE RESTRICT,
    release_manifest_hash char(64) NOT NULL CHECK (release_manifest_hash ~ '^[0-9a-f]{64}$'),
    delivery_fingerprint char(64) NOT NULL UNIQUE CHECK (delivery_fingerprint ~ '^[0-9a-f]{64}$'),
    idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) BETWEEN 8 AND 240),
    privacy text NOT NULL CHECK (privacy IN ('private','unlisted','public')),
    scheduled_for timestamptz NOT NULL,
    next_attempt_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued','processing','retry_wait','succeeded','failed','cancelled'
    )),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count>=0),
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
    current_worker_id text,
    lease_token uuid,
    lease_expires_at timestamptz,
    platform_reference text,
    last_error_code text,
    last_error_message text,
    last_error_retryable boolean,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    cancelled_at timestamptz,
    cancelled_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    UNIQUE (target_id,idempotency_key),
    CHECK (
        status<>'processing'
        OR (current_worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
    ),
    CHECK (
        status<>'succeeded'
        OR (platform_reference IS NOT NULL AND completed_at IS NOT NULL)
    ),
    CHECK (
        status<>'failed'
        OR (last_error_code IS NOT NULL AND last_error_message IS NOT NULL AND completed_at IS NOT NULL)
    ),
    CHECK (
        status<>'cancelled'
        OR (cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL)
    )
);

CREATE INDEX platform_delivery_due_idx
ON football_brief.platform_delivery_requests(status,next_attempt_at,scheduled_for,id)
WHERE status IN ('queued','retry_wait');
CREATE INDEX platform_delivery_release_idx
ON football_brief.platform_delivery_requests(final_release_id,target_id,created_at DESC);

CREATE TABLE football_brief.platform_delivery_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_request_id uuid NOT NULL
        REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    sequence_number integer NOT NULL CHECK (sequence_number>=1),
    cycle_number integer NOT NULL CHECK (cycle_number>=1),
    transport text NOT NULL CHECK (transport IN ('primary','fallback')),
    adapter_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
    request_snapshot jsonb NOT NULL CHECK (jsonb_typeof(request_snapshot)='object'),
    response_payload jsonb,
    provider_request_id text,
    platform_reference text,
    error_code text,
    error_message text,
    retryable boolean,
    worker_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (delivery_request_id,sequence_number),
    CHECK (
        status<>'running'
        OR (finished_at IS NULL AND response_payload IS NULL AND error_code IS NULL)
    ),
    CHECK (
        status<>'succeeded'
        OR (
            finished_at IS NOT NULL
            AND response_payload IS NOT NULL
            AND provider_request_id IS NOT NULL
            AND platform_reference IS NOT NULL
            AND error_code IS NULL
        )
    ),
    CHECK (
        status<>'failed'
        OR (
            finished_at IS NOT NULL
            AND error_code IS NOT NULL
            AND error_message IS NOT NULL
            AND retryable IS NOT NULL
            AND response_payload IS NULL
        )
    )
);

CREATE INDEX platform_delivery_attempts_request_idx
ON football_brief.platform_delivery_attempts(delivery_request_id,sequence_number);
CREATE INDEX platform_delivery_attempts_target_rate_idx
ON football_brief.platform_delivery_attempts(started_at,delivery_request_id);

CREATE TABLE football_brief.platform_delivery_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_request_id uuid REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    target_id uuid REFERENCES football_brief.platform_delivery_targets(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'target_created','target_activated','target_revised','target_unavailable','target_retired',
        'delivery_created','delivery_claimed','primary_attempted','fallback_attempted',
        'delivery_retry_scheduled','delivery_succeeded','delivery_failed','delivery_cancelled',
        'delivery_lease_recovered'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX platform_delivery_events_request_idx
ON football_brief.platform_delivery_events(delivery_request_id,created_at,id);

COMMENT ON TABLE football_brief.platform_delivery_targets IS
    'Versioned platform delivery configuration. P97 execution is limited to simulated adapters.';
COMMENT ON TABLE football_brief.platform_delivery_requests IS
    'Scheduled exact-release delivery state with duplicate-post fingerprint and lease recovery.';
COMMENT ON TABLE football_brief.platform_delivery_attempts IS
    'Append-only primary and fallback adapter calls, provider responses, failures, and platform references.';

COMMIT;
