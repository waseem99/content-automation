-- P128 durable campaign DAG orchestration, capability-aware workers, fair claims,
-- lease recovery and retained million-task acceptance evidence.

BEGIN;

CREATE TABLE football_brief.campaign_task_graphs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    graph_key text NOT NULL CHECK (graph_key ~ '^[a-z0-9][a-z0-9._-]{2,159}$'),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','active','paused','cancel_requested','cancelled','completed','failed','superseded'
    )),
    definition_sha256 char(64) NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    paused_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    cancelled_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    paused_at timestamptz,
    cancelled_at timestamptz,
    completed_at timestamptz,
    UNIQUE (campaign_id,version),
    UNIQUE (graph_key,version),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'paused' OR (paused_by IS NOT NULL AND paused_at IS NOT NULL)),
    CHECK (status<>'cancelled' OR (cancelled_by IS NOT NULL AND cancelled_at IS NOT NULL)),
    CHECK (status<>'completed' OR completed_at IS NOT NULL)
);

CREATE UNIQUE INDEX campaign_task_graph_one_live_idx
ON football_brief.campaign_task_graphs(campaign_id)
WHERE status IN ('active','paused','cancel_requested');

CREATE TABLE football_brief.campaign_task_workers (
    worker_id text PRIMARY KEY CHECK (length(btrim(worker_id)) BETWEEN 3 AND 200),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 240),
    active boolean NOT NULL DEFAULT true,
    capabilities text[] NOT NULL CHECK (cardinality(capabilities)>0),
    max_concurrency integer NOT NULL DEFAULT 1 CHECK (max_concurrency BETWEEN 1 AND 1000),
    heartbeat_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    registered_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX campaign_task_workers_active_idx
ON football_brief.campaign_task_workers(active,heartbeat_at DESC);
CREATE INDEX campaign_task_workers_capabilities_idx
ON football_brief.campaign_task_workers USING gin(capabilities);

CREATE TABLE football_brief.campaign_tasks (
    id bigserial PRIMARY KEY,
    graph_id uuid NOT NULL REFERENCES football_brief.campaign_task_graphs(id) ON DELETE RESTRICT,
    campaign_item_id uuid REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    task_key text NOT NULL CHECK (length(btrim(task_key)) BETWEEN 3 AND 200),
    task_type text NOT NULL CHECK (length(btrim(task_type)) BETWEEN 2 AND 120),
    stage_order integer NOT NULL DEFAULT 1 CHECK (stage_order >= 1),
    required_capabilities text[] NOT NULL CHECK (cardinality(required_capabilities)>0),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'blocked','queued','running','succeeded','failed','cancelled','dead_letter'
    )),
    priority integer NOT NULL DEFAULT 0 CHECK (priority BETWEEN -1000 AND 1000),
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) BETWEEN 8 AND 240),
    input_fingerprint char(64) NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    input_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(input_payload)='object'),
    output_fingerprint char(64) CHECK (output_fingerprint IS NULL OR output_fingerprint ~ '^[0-9a-f]{64}$'),
    output_payload jsonb CHECK (output_payload IS NULL OR jsonb_typeof(output_payload)='object'),
    terminal_fingerprint char(64) CHECK (terminal_fingerprint IS NULL OR terminal_fingerprint ~ '^[0-9a-f]{64}$'),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND max_attempts),
    current_attempt_id bigint,
    current_worker_id text REFERENCES football_brief.campaign_task_workers(worker_id) ON DELETE RESTRICT,
    current_lease_token uuid,
    heartbeat_at timestamptz,
    lease_expires_at timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    cancel_requested boolean NOT NULL DEFAULT false,
    started_at timestamptz,
    finished_at timestamptz,
    error_code text,
    error_details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(error_details)='object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (graph_id,task_key),
    CHECK (status<>'running' OR (
        current_attempt_id IS NOT NULL AND current_worker_id IS NOT NULL
        AND current_lease_token IS NOT NULL AND heartbeat_at IS NOT NULL
        AND lease_expires_at IS NOT NULL
    )),
    CHECK (status NOT IN ('blocked','queued') OR (
        current_attempt_id IS NULL AND current_worker_id IS NULL
        AND current_lease_token IS NULL AND heartbeat_at IS NULL
        AND lease_expires_at IS NULL AND finished_at IS NULL
    )),
    CHECK (status<>'succeeded' OR (
        output_fingerprint IS NOT NULL AND output_payload IS NOT NULL
        AND terminal_fingerprint IS NOT NULL AND finished_at IS NOT NULL
    )),
    CHECK (status NOT IN ('failed','cancelled','dead_letter') OR (
        terminal_fingerprint IS NOT NULL AND finished_at IS NOT NULL
    ))
);

CREATE INDEX campaign_tasks_claim_idx
ON football_brief.campaign_tasks(priority DESC,available_at,stage_order,id)
WHERE status='queued';
CREATE INDEX campaign_tasks_lease_idx
ON football_brief.campaign_tasks(lease_expires_at)
WHERE status='running';
CREATE INDEX campaign_tasks_graph_status_idx
ON football_brief.campaign_tasks(graph_id,status,stage_order,id);
CREATE INDEX campaign_tasks_capabilities_idx
ON football_brief.campaign_tasks USING gin(required_capabilities);

CREATE TABLE football_brief.campaign_task_dependencies (
    task_id bigint NOT NULL REFERENCES football_brief.campaign_tasks(id) ON DELETE RESTRICT,
    depends_on_task_id bigint NOT NULL REFERENCES football_brief.campaign_tasks(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id,depends_on_task_id),
    CHECK (task_id<>depends_on_task_id)
);

CREATE INDEX campaign_task_dependencies_reverse_idx
ON football_brief.campaign_task_dependencies(depends_on_task_id,task_id);

CREATE TABLE football_brief.campaign_task_attempts (
    id bigserial PRIMARY KEY,
    task_id bigint NOT NULL REFERENCES football_brief.campaign_tasks(id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number>=1),
    lease_token uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    worker_id text NOT NULL REFERENCES football_brief.campaign_task_workers(worker_id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'running' CHECK (status IN (
        'running','succeeded','failed','cancelled','timed_out','abandoned'
    )),
    input_fingerprint char(64) NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    output_fingerprint char(64) CHECK (output_fingerprint IS NULL OR output_fingerprint ~ '^[0-9a-f]{64}$'),
    terminal_fingerprint char(64) CHECK (terminal_fingerprint IS NULL OR terminal_fingerprint ~ '^[0-9a-f]{64}$'),
    output_payload jsonb CHECK (output_payload IS NULL OR jsonb_typeof(output_payload)='object'),
    error_code text,
    error_details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(error_details)='object'),
    claimed_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz NOT NULL DEFAULT now(),
    lease_expires_at timestamptz NOT NULL,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (task_id,attempt_number),
    UNIQUE (id,task_id),
    CHECK (status='running' OR finished_at IS NOT NULL),
    CHECK (status<>'succeeded' OR (
        output_fingerprint IS NOT NULL AND output_payload IS NOT NULL
        AND terminal_fingerprint IS NOT NULL
    ))
);

ALTER TABLE football_brief.campaign_tasks
    ADD CONSTRAINT campaign_task_current_attempt_fk
    FOREIGN KEY (current_attempt_id,id)
    REFERENCES football_brief.campaign_task_attempts(id,task_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX campaign_task_attempts_worker_idx
ON football_brief.campaign_task_attempts(worker_id,status,lease_expires_at);

CREATE TABLE football_brief.campaign_task_events (
    id bigserial PRIMARY KEY,
    graph_id uuid NOT NULL REFERENCES football_brief.campaign_task_graphs(id) ON DELETE RESTRICT,
    task_id bigint REFERENCES football_brief.campaign_tasks(id) ON DELETE RESTRICT,
    attempt_id bigint REFERENCES football_brief.campaign_task_attempts(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN (
        'graph_created','graph_activated','graph_paused','graph_resumed','graph_cancelled',
        'tasks_inserted','tasks_claimed','tasks_completed','tasks_failed','leases_recovered',
        'worker_registered','worker_heartbeat','graph_completed'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX campaign_task_events_graph_idx
ON football_brief.campaign_task_events(graph_id,created_at,id);

CREATE TABLE football_brief.dag_acceptance_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    acceptance_key text NOT NULL UNIQUE CHECK (acceptance_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed')),
    requested_tasks bigint NOT NULL CHECK (requested_tasks BETWEEN 1 AND 5000000),
    requested_workers integer NOT NULL CHECK (requested_workers BETWEEN 1 AND 500),
    campaign_count integer NOT NULL CHECK (campaign_count BETWEEN 1 AND 100),
    terminal_tasks bigint NOT NULL DEFAULT 0 CHECK (terminal_tasks>=0),
    succeeded_tasks bigint NOT NULL DEFAULT 0 CHECK (succeeded_tasks>=0),
    duplicate_terminal_attempts bigint NOT NULL DEFAULT 0 CHECK (duplicate_terminal_attempts>=0),
    recovered_leases bigint NOT NULL DEFAULT 0 CHECK (recovered_leases>=0),
    fairness_spread bigint NOT NULL DEFAULT 0 CHECK (fairness_spread>=0),
    paused_claims bigint NOT NULL DEFAULT 0 CHECK (paused_claims>=0),
    cancelled_tasks bigint NOT NULL DEFAULT 0 CHECK (cancelled_tasks>=0),
    timings_ms jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(timings_ms)='object'),
    counters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(counters)='object'),
    environment jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(environment)='object'),
    error jsonb CHECK (error IS NULL OR jsonb_typeof(error)='object'),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='running' OR completed_at IS NOT NULL),
    CHECK (status<>'passed' OR (
        terminal_tasks=requested_tasks
        AND succeeded_tasks=requested_tasks
        AND duplicate_terminal_attempts=0
        AND recovered_leases>0
        AND fairness_spread<=1
        AND paused_claims=0
    ))
);

CREATE OR REPLACE FUNCTION football_brief.protect_campaign_task_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Campaign tasks cannot be deleted'; END IF;
    IF OLD.status IN ('succeeded','cancelled','dead_letter') THEN
        RAISE EXCEPTION 'Terminal campaign tasks are immutable';
    END IF;
    IF NEW.graph_id IS DISTINCT FROM OLD.graph_id
       OR NEW.campaign_item_id IS DISTINCT FROM OLD.campaign_item_id
       OR NEW.task_key IS DISTINCT FROM OLD.task_key
       OR NEW.task_type IS DISTINCT FROM OLD.task_type
       OR NEW.stage_order IS DISTINCT FROM OLD.stage_order
       OR NEW.required_capabilities IS DISTINCT FROM OLD.required_capabilities
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.input_payload IS DISTINCT FROM OLD.input_payload
       OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Campaign task identity and inputs are immutable';
    END IF;
    IF NEW.attempt_count<OLD.attempt_count THEN
        RAISE EXCEPTION 'Campaign task attempt count cannot decrease';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER campaign_task_identity_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_tasks
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_task_identity();

CREATE OR REPLACE FUNCTION football_brief.protect_campaign_task_attempt()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Campaign task attempts cannot be deleted'; END IF;
    IF OLD.status<>'running' THEN RAISE EXCEPTION 'Terminal campaign task attempts are immutable'; END IF;
    IF NEW.task_id IS DISTINCT FROM OLD.task_id
       OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
       OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
       OR NEW.worker_id IS DISTINCT FROM OLD.worker_id
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.claimed_at IS DISTINCT FROM OLD.claimed_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Campaign task attempt identity is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER campaign_task_attempt_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_task_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_task_attempt();

CREATE OR REPLACE FUNCTION football_brief.protect_campaign_task_evidence()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Campaign task dependencies and events are immutable';
END;
$$;

CREATE TRIGGER campaign_task_dependency_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_task_dependencies
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_task_evidence();
CREATE TRIGGER campaign_task_event_immutable
BEFORE UPDATE OR DELETE ON football_brief.campaign_task_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_campaign_task_evidence();

CREATE TRIGGER campaign_task_workers_touch_updated_at
BEFORE UPDATE ON football_brief.campaign_task_workers
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();
CREATE TRIGGER campaign_tasks_touch_updated_at
BEFORE UPDATE ON football_brief.campaign_tasks
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

COMMENT ON TABLE football_brief.campaign_tasks IS
    'Database-native campaign DAG tasks with capability requirements, immutable inputs and durable leases.';
COMMENT ON TABLE football_brief.dag_acceptance_runs IS
    'Retained evidence for million-task, 100-worker, fairness and lease-recovery acceptance.';

COMMIT;
