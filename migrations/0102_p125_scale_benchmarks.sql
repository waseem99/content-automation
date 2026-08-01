-- P125 retained scale-benchmark evidence for the database-native control plane.
-- These measurements do not claim final-video rendering capacity.

BEGIN;

CREATE TABLE football_brief.scale_benchmark_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_key text NOT NULL UNIQUE CHECK (benchmark_key ~ '^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$'),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed','partial')),
    campaign_id uuid REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    requested_items integer NOT NULL CHECK (requested_items BETWEEN 1 AND 20000),
    requested_checks bigint NOT NULL CHECK (requested_checks BETWEEN 0 AND 5000000),
    inserted_items integer NOT NULL DEFAULT 0 CHECK (inserted_items >= 0),
    inserted_runs integer NOT NULL DEFAULT 0 CHECK (inserted_runs >= 0),
    inserted_checks bigint NOT NULL DEFAULT 0 CHECK (inserted_checks >= 0),
    duplicate_items integer NOT NULL DEFAULT 0 CHECK (duplicate_items >= 0),
    duplicate_checks bigint NOT NULL DEFAULT 0 CHECK (duplicate_checks >= 0),
    claim_sample integer NOT NULL DEFAULT 0 CHECK (claim_sample >= 0),
    timings_ms jsonb NOT NULL DEFAULT '{}'::jsonb,
    counters jsonb NOT NULL DEFAULT '{}'::jsonb,
    environment jsonb NOT NULL DEFAULT '{}'::jsonb,
    error jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX scale_benchmark_runs_created_idx
ON football_brief.scale_benchmark_runs(created_at DESC,status);

COMMENT ON TABLE football_brief.scale_benchmark_runs IS
    'Measured database control-plane evidence only; never interpreted as final video rendering throughput.';

COMMIT;
