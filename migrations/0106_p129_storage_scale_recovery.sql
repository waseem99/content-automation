-- P129 retained evidence for 100,000 canonical local/Google Drive location records
-- and verified missing-local recovery from an available Drive copy.

BEGIN;

CREATE TABLE football_brief.asset_storage_recovery_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    source_location_id uuid NOT NULL REFERENCES football_brief.asset_storage_locations(id) ON DELETE RESTRICT,
    destination_location_id uuid NOT NULL REFERENCES football_brief.asset_storage_locations(id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('started','succeeded','failed')),
    expected_sha256 char(64) NOT NULL CHECK (expected_sha256 ~ '^[0-9a-f]{64}$'),
    observed_sha256 char(64) CHECK (observed_sha256 IS NULL OR observed_sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint CHECK (size_bytes IS NULL OR size_bytes>=0),
    error_code text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='started' OR completed_at IS NOT NULL),
    CHECK (status<>'succeeded' OR observed_sha256=expected_sha256)
);

CREATE INDEX asset_storage_recovery_events_asset_idx
ON football_brief.asset_storage_recovery_events(asset_id,created_at DESC);

CREATE TABLE football_brief.storage_scale_acceptance_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    acceptance_key text NOT NULL UNIQUE CHECK (acceptance_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed')),
    requested_assets integer NOT NULL CHECK (requested_assets BETWEEN 1 AND 1000000),
    requested_locations integer NOT NULL CHECK (requested_locations BETWEEN 2 AND 2000000),
    retained_assets integer NOT NULL DEFAULT 0 CHECK (retained_assets>=0),
    retained_locations integer NOT NULL DEFAULT 0 CHECK (retained_locations>=0),
    duplicate_locations integer NOT NULL DEFAULT 0 CHECK (duplicate_locations>=0),
    mismatches_detected integer NOT NULL DEFAULT 0 CHECK (mismatches_detected>=0),
    missing_detected integer NOT NULL DEFAULT 0 CHECK (missing_detected>=0),
    recovered_local_copies integer NOT NULL DEFAULT 0 CHECK (recovered_local_copies>=0),
    canonical_identity_changes integer NOT NULL DEFAULT 0 CHECK (canonical_identity_changes>=0),
    drive_outage_local_failures integer NOT NULL DEFAULT 0 CHECK (drive_outage_local_failures>=0),
    timings_ms jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(timings_ms)='object'),
    counters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(counters)='object'),
    environment jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(environment)='object'),
    error jsonb CHECK (error IS NULL OR jsonb_typeof(error)='object'),
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='running' OR completed_at IS NOT NULL),
    CHECK (status<>'passed' OR (
        retained_assets=requested_assets
        AND retained_locations=requested_locations
        AND duplicate_locations=0
        AND mismatches_detected>=1
        AND missing_detected>=1
        AND recovered_local_copies>=1
        AND canonical_identity_changes=0
        AND drive_outage_local_failures=0
    ))
);

CREATE OR REPLACE FUNCTION football_brief.protect_storage_recovery_evidence()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Storage recovery evidence is immutable';
END;
$$;

CREATE TRIGGER asset_storage_recovery_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.asset_storage_recovery_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_storage_recovery_evidence();

COMMENT ON TABLE football_brief.storage_scale_acceptance_runs IS
    'Retained 100k-location control-plane and real local/Drive recovery acceptance evidence.';

COMMIT;
