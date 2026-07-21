-- Unified, content-version-bound generation and delivery job queue.
-- Provider secrets and media bytes remain outside PostgreSQL.

BEGIN;

CREATE TABLE football_brief.generation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version >= 1),
    production_workflow_id uuid REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    production_workflow_version_id uuid REFERENCES football_brief.production_workflow_versions(id) ON DELETE RESTRICT,
    job_type text NOT NULL CHECK (job_type IN (
        'concept', 'script', 'narration', 'keyframe', 'preview', 'premium_clip',
        'assembly', 'caption', 'thumbnail', 'package', 'publishing'
    )),
    provider text,
    model_id text,
    preferred_worker_id text,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'succeeded', 'failed', 'cancelled', 'dead_letter'
    )),
    priority integer NOT NULL DEFAULT 0 CHECK (priority BETWEEN -1000 AND 1000),
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) BETWEEN 8 AND 240),
    input_fingerprint char(64) NOT NULL,
    input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_fingerprint char(64),
    output_payload jsonb,
    timeout_seconds integer NOT NULL DEFAULT 300 CHECK (timeout_seconds BETWEEN 5 AND 86400),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0 AND attempt_count <= max_attempts),
    current_attempt_id uuid,
    current_worker_id text,
    estimated_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    reserved_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (reserved_cost_usd >= 0),
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    heartbeat_at timestamptz,
    lease_expires_at timestamptz,
    finished_at timestamptz,
    cancelled_at timestamptz,
    cancelled_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    error_code text,
    error_message text,
    error_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    legacy_source jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT generation_job_running_has_lease CHECK (
        status <> 'running' OR (
            current_attempt_id IS NOT NULL
            AND nullif(btrim(current_worker_id), '') IS NOT NULL
            AND heartbeat_at IS NOT NULL
            AND lease_expires_at IS NOT NULL
        )
    ),
    CONSTRAINT generation_job_queued_has_no_lease CHECK (
        status <> 'queued' OR (
            current_attempt_id IS NULL
            AND current_worker_id IS NULL
            AND heartbeat_at IS NULL
            AND lease_expires_at IS NULL
            AND finished_at IS NULL
        )
    ),
    CONSTRAINT generation_job_succeeded_has_output CHECK (
        status <> 'succeeded' OR (
            output_payload IS NOT NULL
            AND output_fingerprint IS NOT NULL
            AND finished_at IS NOT NULL
        )
    ),
    CONSTRAINT generation_job_terminal_has_finish CHECK (
        status NOT IN ('failed', 'cancelled', 'dead_letter') OR finished_at IS NOT NULL
    ),
    CONSTRAINT generation_job_cancelled_has_actor CHECK (
        status <> 'cancelled' OR (cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL)
    ),
    CONSTRAINT generation_job_workflow_version_pair CHECK (
        production_workflow_version_id IS NULL OR production_workflow_id IS NOT NULL
    )
);

CREATE INDEX generation_jobs_claim_idx
ON football_brief.generation_jobs (priority DESC, available_at, queued_at, id)
WHERE status = 'queued';

CREATE INDEX generation_jobs_lease_idx
ON football_brief.generation_jobs (lease_expires_at)
WHERE status = 'running';

CREATE INDEX generation_jobs_content_idx
ON football_brief.generation_jobs (portfolio_content_id, content_version, status, job_type);

CREATE INDEX generation_jobs_worker_idx
ON football_brief.generation_jobs (current_worker_id, status)
WHERE current_worker_id IS NOT NULL;

CREATE TABLE football_brief.generation_job_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number >= 1),
    lease_token uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    worker_id text NOT NULL CHECK (length(btrim(worker_id)) BETWEEN 1 AND 200),
    status text NOT NULL DEFAULT 'running' CHECK (status IN (
        'running', 'succeeded', 'failed', 'cancelled', 'timed_out', 'abandoned'
    )),
    input_fingerprint char(64) NOT NULL,
    output_fingerprint char(64),
    output_payload jsonb,
    provider_request_id text,
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    retryable boolean,
    error_code text,
    error_message text,
    error_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    claimed_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz NOT NULL DEFAULT now(),
    lease_expires_at timestamptz NOT NULL,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id, attempt_number),
    UNIQUE (id, job_id),
    CONSTRAINT generation_attempt_running_has_no_finish CHECK (
        status <> 'running' OR finished_at IS NULL
    ),
    CONSTRAINT generation_attempt_terminal_has_finish CHECK (
        status = 'running' OR finished_at IS NOT NULL
    ),
    CONSTRAINT generation_attempt_success_has_output CHECK (
        status <> 'succeeded' OR (output_payload IS NOT NULL AND output_fingerprint IS NOT NULL)
    )
);

ALTER TABLE football_brief.generation_jobs
    ADD CONSTRAINT generation_job_current_attempt_fk
    FOREIGN KEY (current_attempt_id, id)
    REFERENCES football_brief.generation_job_attempts(id, job_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX generation_job_attempts_job_idx
ON football_brief.generation_job_attempts (job_id, attempt_number DESC);

CREATE INDEX generation_job_attempts_worker_idx
ON football_brief.generation_job_attempts (worker_id, status, lease_expires_at);

CREATE TABLE football_brief.generation_job_dependencies (
    job_id uuid NOT NULL REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    depends_on_job_id uuid NOT NULL REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, depends_on_job_id),
    CONSTRAINT generation_job_dependency_not_self CHECK (job_id <> depends_on_job_id)
);

CREATE INDEX generation_job_dependencies_reverse_idx
ON football_brief.generation_job_dependencies (depends_on_job_id, job_id);

CREATE TABLE football_brief.generation_job_events (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    attempt_id uuid REFERENCES football_brief.generation_job_attempts(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'enqueued', 'idempotent_reuse', 'claimed', 'heartbeat', 'succeeded', 'failed',
        'cancelled', 'retried', 'recovered', 'timed_out', 'dead_lettered',
        'legacy_imported', 'content_version_superseded'
    )),
    actor text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX generation_job_events_job_idx
ON football_brief.generation_job_events (job_id, created_at, id);

CREATE OR REPLACE FUNCTION football_brief.protect_generation_job_core()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Generation jobs cannot be deleted';
    END IF;

    IF OLD.status IN ('succeeded', 'cancelled', 'dead_letter') THEN
        RAISE EXCEPTION 'Terminal generation jobs are immutable';
    END IF;

    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.production_workflow_id IS DISTINCT FROM OLD.production_workflow_id
       OR NEW.production_workflow_version_id IS DISTINCT FROM OLD.production_workflow_version_id
       OR NEW.job_type IS DISTINCT FROM OLD.job_type
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.input_payload IS DISTINCT FROM OLD.input_payload
       OR NEW.timeout_seconds IS DISTINCT FROM OLD.timeout_seconds
       OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.legacy_source IS DISTINCT FROM OLD.legacy_source THEN
        RAISE EXCEPTION 'Generation job identity and inputs are immutable';
    END IF;

    IF NEW.attempt_count < OLD.attempt_count THEN
        RAISE EXCEPTION 'Generation job attempt count cannot decrease';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled') THEN
            NULL;
        ELSIF OLD.status = 'running' AND NEW.status IN (
            'queued', 'succeeded', 'failed', 'cancelled', 'dead_letter'
        ) THEN
            NULL;
        ELSIF OLD.status = 'failed' AND NEW.status IN ('queued', 'cancelled', 'dead_letter') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid generation job status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_core_immutable
BEFORE UPDATE OR DELETE ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_generation_job_core();

CREATE TRIGGER generation_jobs_touch_updated_at
BEFORE UPDATE ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE OR REPLACE FUNCTION football_brief.protect_generation_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Generation job attempts cannot be deleted';
    END IF;
    IF OLD.status <> 'running' THEN
        RAISE EXCEPTION 'Terminal generation job attempts are immutable';
    END IF;
    IF NEW.job_id IS DISTINCT FROM OLD.job_id
       OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
       OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
       OR NEW.worker_id IS DISTINCT FROM OLD.worker_id
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.claimed_at IS DISTINCT FROM OLD.claimed_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Generation job attempt identity is immutable';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status
       AND NEW.status NOT IN ('succeeded', 'failed', 'cancelled', 'timed_out', 'abandoned') THEN
        RAISE EXCEPTION 'Invalid generation attempt status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_attempt_immutable
BEFORE UPDATE OR DELETE ON football_brief.generation_job_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_generation_attempt();

CREATE OR REPLACE FUNCTION football_brief.protect_generation_job_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Generation job dependencies and events are immutable';
END;
$$;

CREATE TRIGGER generation_job_dependency_immutable
BEFORE UPDATE OR DELETE ON football_brief.generation_job_dependencies
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_generation_job_evidence();

CREATE TRIGGER generation_job_event_immutable
BEFORE UPDATE OR DELETE ON football_brief.generation_job_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_generation_job_evidence();

COMMENT ON TABLE football_brief.generation_jobs IS
    'Unified queue for generation and delivery work. Idempotency is global and inputs are content-version-bound.';
COMMENT ON TABLE football_brief.generation_job_attempts IS
    'Every worker claim is retained with a unique lease token so stale workers cannot complete newer attempts.';
COMMENT ON TABLE football_brief.generation_job_events IS
    'Append-only operator and worker lifecycle evidence. Heartbeat rows may be sampled by the service.';

COMMIT;
