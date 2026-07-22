-- Production operations evidence: releases, backups, restore drills, alerts, and rollback records.

BEGIN;

CREATE TABLE football_brief.operations_releases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    environment text NOT NULL CHECK (environment IN ('staging','production')),
    release_key text NOT NULL UNIQUE CHECK (release_key ~ '^[A-Za-z0-9._:-]{8,200}$'),
    git_sha char(40) NOT NULL CHECK (git_sha ~ '^[0-9a-f]{40}$'),
    image_digest text NOT NULL CHECK (image_digest ~ '^sha256:[0-9a-f]{64}$'),
    configuration_digest char(64) NOT NULL CHECK (configuration_digest ~ '^[0-9a-f]{64}$'),
    migration_head text NOT NULL CHECK (length(btrim(migration_head)) BETWEEN 8 AND 200),
    previous_release_id uuid REFERENCES football_brief.operations_releases(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'planned' CHECK (status IN (
        'planned','deploying','healthy','failed','rolled_back','retired'
    )),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    deploying_at timestamptz,
    healthy_at timestamptz,
    failed_at timestamptz,
    rolled_back_at timestamptz,
    retired_at timestamptz,
    CHECK (previous_release_id IS NULL OR environment IS NOT NULL)
);

CREATE UNIQUE INDEX operations_one_deploying_release_idx
ON football_brief.operations_releases(environment)
WHERE status='deploying';

CREATE INDEX operations_releases_environment_idx
ON football_brief.operations_releases(environment,created_at DESC);

CREATE TABLE football_brief.operations_backup_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    environment text NOT NULL CHECK (environment IN ('staging','production')),
    backup_key text NOT NULL UNIQUE CHECK (backup_key ~ '^[A-Za-z0-9._:-]{8,240}$'),
    database_object_ref text NOT NULL CHECK (length(btrim(database_object_ref)) BETWEEN 3 AND 1000),
    artifact_object_ref text NOT NULL CHECK (length(btrim(artifact_object_ref)) BETWEEN 3 AND 1000),
    database_sha256 char(64) NOT NULL CHECK (database_sha256 ~ '^[0-9a-f]{64}$'),
    artifact_sha256 char(64) NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    migration_head text NOT NULL CHECK (length(btrim(migration_head)) BETWEEN 8 AND 200),
    database_bytes bigint NOT NULL CHECK (database_bytes>0),
    artifact_bytes bigint NOT NULL CHECK (artifact_bytes>=0),
    status text NOT NULL DEFAULT 'available' CHECK (status IN ('available','restored','expired')),
    retention_until timestamptz NOT NULL,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    restored_at timestamptz,
    expired_at timestamptz,
    CHECK (retention_until>created_at)
);

CREATE INDEX operations_backup_sets_environment_idx
ON football_brief.operations_backup_sets(environment,created_at DESC);

CREATE TABLE football_brief.operations_drill_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    environment text NOT NULL CHECK (environment IN ('staging','production')),
    drill_kind text NOT NULL CHECK (drill_kind IN (
        'staging_recreate','database_restore','artifact_restore','worker_restart',
        'release_rollback','api_health_alert','queue_stall_alert','worker_failure_alert',
        'low_storage_alert','security_scan'
    )),
    release_id uuid REFERENCES football_brief.operations_releases(id) ON DELETE RESTRICT,
    backup_set_id uuid REFERENCES football_brief.operations_backup_sets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed')),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence)='object'),
    evidence_digest char(64),
    started_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='running' OR (completed_at IS NOT NULL AND evidence_digest IS NOT NULL)),
    CHECK (status<>'running' OR completed_at IS NULL)
);

CREATE INDEX operations_drill_runs_kind_idx
ON football_brief.operations_drill_runs(environment,drill_kind,started_at DESC);

CREATE TABLE football_brief.operations_alert_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    environment text NOT NULL CHECK (environment IN ('staging','production')),
    alert_key text NOT NULL CHECK (length(btrim(alert_key)) BETWEEN 3 AND 240),
    alert_kind text NOT NULL CHECK (alert_kind IN (
        'api_unhealthy','queue_stalled','worker_failed','storage_low','budget_threshold',
        'backup_stale','restore_failed','security_scan_failed'
    )),
    severity text NOT NULL CHECK (severity IN ('info','warning','critical')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved')),
    source text NOT NULL CHECK (length(btrim(source)) BETWEEN 2 AND 160),
    details jsonb NOT NULL CHECK (jsonb_typeof(details)='object'),
    details_digest char(64) NOT NULL CHECK (details_digest ~ '^[0-9a-f]{64}$'),
    detected_at timestamptz NOT NULL DEFAULT now(),
    acknowledged_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    acknowledged_at timestamptz,
    resolved_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    UNIQUE (environment,alert_key,details_digest),
    CHECK (status<>'acknowledged' OR (acknowledged_by IS NOT NULL AND acknowledged_at IS NOT NULL)),
    CHECK (status<>'resolved' OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);

CREATE INDEX operations_alert_events_open_idx
ON football_brief.operations_alert_events(environment,severity,detected_at DESC)
WHERE status<>'resolved';

CREATE TABLE football_brief.operations_restore_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_set_id uuid NOT NULL REFERENCES football_brief.operations_backup_sets(id) ON DELETE RESTRICT,
    environment text NOT NULL CHECK (environment IN ('staging','production')),
    database_restored boolean NOT NULL,
    artifacts_restored boolean NOT NULL,
    migration_head_verified boolean NOT NULL,
    database_sha256_verified boolean NOT NULL,
    artifact_sha256_verified boolean NOT NULL,
    verification jsonb NOT NULL CHECK (jsonb_typeof(verification)='object'),
    restored_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    restored_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        database_restored AND artifacts_restored AND migration_head_verified
        AND database_sha256_verified AND artifact_sha256_verified
    )
);

CREATE INDEX operations_restore_events_backup_idx
ON football_brief.operations_restore_events(backup_set_id,restored_at DESC);

COMMENT ON TABLE football_brief.operations_releases IS
    'Environment-neutral release identity and rollback lineage; secrets and environment values remain external.';
COMMENT ON TABLE football_brief.operations_backup_sets IS
    'Database and artifact backup references, checksums, sizes, retention, and migration head; bytes remain external.';
COMMENT ON TABLE football_brief.operations_drill_runs IS
    'Recorded staging, restore, restart, rollback, alert, and security drill evidence.';
COMMENT ON TABLE football_brief.operations_alert_events IS
    'Deduplicated operational alert evidence for API, queue, worker, storage, budget, backup, restore, and security conditions.';

COMMIT;
