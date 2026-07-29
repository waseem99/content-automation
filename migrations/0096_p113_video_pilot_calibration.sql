-- P113 dual-model video pilot calibration and model-use policy.
-- Forward-only. This migration records measured evidence; it does not download models,
-- enable paid generation, approve public publishing, or invent benchmark results.

BEGIN;

CREATE TABLE football_brief.video_model_use_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key text NOT NULL CHECK (provider_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    model_key text NOT NULL CHECK (model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$'),
    model_display_name text NOT NULL CHECK (length(btrim(model_display_name)) BETWEEN 2 AND 200),
    version integer NOT NULL CHECK (version >= 1),
    parent_policy_id uuid REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    license_name text NOT NULL CHECK (length(btrim(license_name)) BETWEEN 2 AND 300),
    license_spdx text,
    terms_url text NOT NULL CHECK (terms_url ~* '^https://'),
    evidence_digest char(64) NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_recorded_at timestamptz NOT NULL,
    commercial_use_allowed boolean NOT NULL DEFAULT false,
    allowed_use_scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
    allowed_territories text[] NOT NULL DEFAULT ARRAY[]::text[],
    prohibited_territories text[] NOT NULL DEFAULT ARRAY[]::text[],
    requires_written_clearance boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (provider_key, model_key, version),
    CHECK (version = 1 OR parent_policy_id IS NOT NULL),
    CHECK (version <> 1 OR parent_policy_id IS NULL),
    CHECK (status <> 'active' OR (activated_at IS NOT NULL AND activated_by IS NOT NULL)),
    CHECK (status <> 'retired' OR (retired_at IS NOT NULL AND retired_by IS NOT NULL)),
    CHECK (allowed_use_scopes <@ ARRAY['internal','territory_limited','global_public']::text[])
);

CREATE UNIQUE INDEX video_model_use_policy_one_active_idx
ON football_brief.video_model_use_policies (provider_key, model_key)
WHERE status='active';

CREATE INDEX video_model_use_policy_lookup_idx
ON football_brief.video_model_use_policies (status, provider_key, model_key, version DESC);

CREATE TABLE football_brief.video_pilot_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_key text NOT NULL UNIQUE CHECK (run_key ~ '^[a-z0-9][a-z0-9._-]{2,99}$'),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 300),
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','running','closed','cancelled')),
    target_videos integer NOT NULL DEFAULT 3 CHECK (target_videos BETWEEN 1 AND 20),
    target_attempts integer NOT NULL DEFAULT 30 CHECK (target_attempts BETWEEN 1 AND 1000),
    hardware_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(hardware_snapshot)='object'),
    software_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(software_snapshot)='object'),
    baseline_assumptions jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(baseline_assumptions)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    started_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    closed_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    closed_at timestamptz,
    CHECK (status <> 'running' OR (started_at IS NOT NULL AND started_by IS NOT NULL)),
    CHECK (status NOT IN ('closed','cancelled') OR (closed_at IS NOT NULL AND closed_by IS NOT NULL))
);

CREATE TABLE football_brief.video_pilot_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_run_id uuid NOT NULL REFERENCES football_brief.video_pilot_runs(id) ON DELETE RESTRICT,
    case_key text NOT NULL CHECK (case_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 300),
    shot_class text NOT NULL CHECK (shot_class IN (
        'easy_motion','people_animals','product','map_diagram','transition','hero'
    )),
    difficulty text NOT NULL CHECK (difficulty IN ('low','medium','high')),
    distribution_scope text NOT NULL CHECK (distribution_scope IN ('internal','territory_limited','global_public')),
    release_territories text[] NOT NULL DEFAULT ARRAY[]::text[],
    target_duration_seconds numeric(10,3) NOT NULL CHECK (target_duration_seconds BETWEEN 1 AND 15),
    prompt text NOT NULL CHECK (length(btrim(prompt)) BETWEEN 3 AND 10000),
    negative_prompt text,
    input_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    required_model_keys text[] NOT NULL DEFAULT ARRAY[]::text[],
    acceptance_criteria jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(acceptance_criteria)='object'),
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','ready','running','completed','cancelled')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_run_id, case_key)
);

CREATE INDEX video_pilot_cases_run_idx
ON football_brief.video_pilot_cases (pilot_run_id, shot_class, difficulty, status, case_key);

CREATE TABLE football_brief.video_pilot_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_case_id uuid NOT NULL REFERENCES football_brief.video_pilot_cases(id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number BETWEEN 1 AND 100),
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    renderer_catalogue_entry_id uuid REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    generation_job_id uuid REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    workflow_key text NOT NULL CHECK (length(btrim(workflow_key)) BETWEEN 2 AND 200),
    workflow_sha256 char(64) NOT NULL CHECK (workflow_sha256 ~ '^[0-9a-f]{64}$'),
    checkpoint_sha256 char(64) NOT NULL CHECK (checkpoint_sha256 ~ '^[0-9a-f]{64}$'),
    seed bigint NOT NULL,
    width integer NOT NULL CHECK (width BETWEEN 256 AND 8192),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 8192),
    fps integer NOT NULL CHECK (fps BETWEEN 1 AND 240),
    frame_count integer NOT NULL CHECK (frame_count BETWEEN 1 AND 10000),
    inference_steps integer NOT NULL CHECK (inference_steps BETWEEN 1 AND 500),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','succeeded','failed','cancelled')),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    wall_clock_ms bigint CHECK (wall_clock_ms IS NULL OR wall_clock_ms >= 0),
    gpu_active_ms bigint CHECK (gpu_active_ms IS NULL OR gpu_active_ms >= 0),
    peak_vram_mib integer CHECK (peak_vram_mib IS NULL OR peak_vram_mib >= 0),
    peak_system_ram_mib integer CHECK (peak_system_ram_mib IS NULL OR peak_system_ram_mib >= 0),
    average_gpu_temperature_c numeric(6,2),
    peak_gpu_temperature_c numeric(6,2),
    average_gpu_power_w numeric(10,3),
    peak_gpu_power_w numeric(10,3),
    output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    external_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_cost_usd >= 0),
    failure_code text,
    failure_message text,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metrics)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_case_id, attempt_number),
    CHECK (
        (status='running' AND completed_at IS NULL)
        OR (status<>'running' AND completed_at IS NOT NULL)
    ),
    CHECK (status<>'succeeded' OR output_asset_id IS NOT NULL),
    CHECK (status<>'failed' OR failure_code IS NOT NULL)
);

CREATE UNIQUE INDEX video_pilot_attempt_generation_job_idx
ON football_brief.video_pilot_attempts (generation_job_id)
WHERE generation_job_id IS NOT NULL;

CREATE INDEX video_pilot_attempt_case_idx
ON football_brief.video_pilot_attempts (pilot_case_id, attempt_number, status);

CREATE TABLE football_brief.video_pilot_attempt_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_attempt_id uuid NOT NULL REFERENCES football_brief.video_pilot_attempts(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('accepted','rejected','needs_revision')),
    motion_quality numeric(5,2) NOT NULL CHECK (motion_quality BETWEEN 0 AND 100),
    reference_consistency numeric(5,2) NOT NULL CHECK (reference_consistency BETWEEN 0 AND 100),
    artifact_control numeric(5,2) NOT NULL CHECK (artifact_control BETWEEN 0 AND 100),
    composition_quality numeric(5,2) NOT NULL CHECK (composition_quality BETWEEN 0 AND 100),
    defect_tags text[] NOT NULL DEFAULT ARRAY[]::text[],
    notes text NOT NULL CHECK (length(btrim(notes)) BETWEEN 3 AND 5000),
    reviewed_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX video_pilot_attempt_reviews_idx
ON football_brief.video_pilot_attempt_reviews (pilot_attempt_id, reviewed_at DESC, id DESC);

CREATE TABLE football_brief.video_pilot_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_run_id uuid NOT NULL REFERENCES football_brief.video_pilot_runs(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    report_snapshot jsonb NOT NULL CHECK (jsonb_typeof(report_snapshot)='object'),
    generated_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_run_id, version)
);

CREATE OR REPLACE FUNCTION football_brief.protect_video_pilot_attempt_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status <> 'running' THEN
        RAISE EXCEPTION 'Terminal pilot attempts are immutable';
    END IF;
    IF NEW.pilot_case_id IS DISTINCT FROM OLD.pilot_case_id
       OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
       OR NEW.model_policy_id IS DISTINCT FROM OLD.model_policy_id
       OR NEW.renderer_catalogue_entry_id IS DISTINCT FROM OLD.renderer_catalogue_entry_id
       OR NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
       OR NEW.workflow_key IS DISTINCT FROM OLD.workflow_key
       OR NEW.workflow_sha256 IS DISTINCT FROM OLD.workflow_sha256
       OR NEW.checkpoint_sha256 IS DISTINCT FROM OLD.checkpoint_sha256
       OR NEW.seed IS DISTINCT FROM OLD.seed
       OR NEW.width IS DISTINCT FROM OLD.width
       OR NEW.height IS DISTINCT FROM OLD.height
       OR NEW.fps IS DISTINCT FROM OLD.fps
       OR NEW.frame_count IS DISTINCT FROM OLD.frame_count
       OR NEW.inference_steps IS DISTINCT FROM OLD.inference_steps
       OR NEW.started_at IS DISTINCT FROM OLD.started_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Pilot attempt identity and generation settings are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER video_pilot_attempt_identity_valid
BEFORE UPDATE ON football_brief.video_pilot_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_video_pilot_attempt_identity();

CREATE OR REPLACE FUNCTION football_brief.protect_video_pilot_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Video pilot evidence is append-only';
END;
$$;

CREATE TRIGGER video_pilot_attempt_reviews_append_only
BEFORE UPDATE OR DELETE ON football_brief.video_pilot_attempt_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_video_pilot_append_only();

CREATE TRIGGER video_pilot_reports_append_only
BEFORE UPDATE OR DELETE ON football_brief.video_pilot_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_video_pilot_append_only();

CREATE TRIGGER video_model_use_policy_append_only
BEFORE UPDATE OR DELETE ON football_brief.video_model_use_policies
FOR EACH ROW
WHEN (OLD.status IN ('active','retired'))
EXECUTE FUNCTION football_brief.protect_video_pilot_append_only();

COMMENT ON TABLE football_brief.video_model_use_policies IS
    'Versioned commercial-use, license and territory policy for each local or managed video model.';
COMMENT ON TABLE football_brief.video_pilot_runs IS
    'Measured dual-model pilot baseline. Hardware and software snapshots are evidence, not theoretical promises.';
COMMENT ON TABLE football_brief.video_pilot_attempts IS
    'Clip-level generation settings, timing, hardware metrics, cost and artifact lineage for the P113 pilot.';
COMMENT ON TABLE football_brief.video_pilot_attempt_reviews IS
    'Human creative acceptance evidence kept separately from automated generation metrics.';

COMMIT;
