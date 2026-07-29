-- P114 local Wan2.2 / HunyuanVideo renderer foundation.
-- Adds a dedicated zero-fee local_clip job type and immutable workflow/execution lineage.

BEGIN;

DO $$
DECLARE
    constraint_row record;
BEGIN
    FOR constraint_row IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'football_brief.generation_jobs'::regclass
          AND contype = 'c'
          AND conname LIKE 'generation_jobs_job_type%check'
    LOOP
        EXECUTE format(
            'ALTER TABLE football_brief.generation_jobs DROP CONSTRAINT %I',
            constraint_row.conname
        );
    END LOOP;
END;
$$;

ALTER TABLE football_brief.generation_jobs
    ADD CONSTRAINT generation_jobs_job_type_p114_check
    CHECK (job_type IN (
        'concept','script','narration','keyframe','preview','local_clip','premium_clip',
        'assembly','caption','thumbnail','package','publishing'
    ));

CREATE TABLE football_brief.local_video_workflows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key text NOT NULL CHECK (provider_key IN ('wan-ai','tencent-hunyuan')),
    model_key text NOT NULL CHECK (length(btrim(model_key)) BETWEEN 2 AND 200),
    workflow_key text NOT NULL CHECK (workflow_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    version integer NOT NULL CHECK (version >= 1),
    parent_workflow_id uuid REFERENCES football_brief.local_video_workflows(id) ON DELETE RESTRICT,
    operation text NOT NULL CHECK (operation IN (
        'image_to_video','start_end_frame','transition','video_super_resolution'
    )),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    workflow_path text NOT NULL CHECK (length(btrim(workflow_path)) BETWEEN 3 AND 1000),
    workflow_sha256 char(64) NOT NULL CHECK (workflow_sha256 ~ '^[0-9a-f]{64}$'),
    checkpoint_sha256 char(64) NOT NULL CHECK (checkpoint_sha256 ~ '^[0-9a-f]{64}$'),
    renderer_catalogue_entry_id uuid REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    supported_resolutions jsonb NOT NULL CHECK (jsonb_typeof(supported_resolutions)='array'),
    min_duration_seconds numeric(10,3) NOT NULL CHECK (min_duration_seconds > 0),
    max_duration_seconds numeric(10,3) NOT NULL CHECK (max_duration_seconds >= min_duration_seconds),
    default_fps integer NOT NULL DEFAULT 24 CHECK (default_fps BETWEEN 1 AND 120),
    default_steps integer NOT NULL CHECK (default_steps BETWEEN 1 AND 500),
    capabilities jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(capabilities)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (provider_key,model_key,workflow_key,version),
    CHECK (version = 1 OR parent_workflow_id IS NOT NULL),
    CHECK (version <> 1 OR parent_workflow_id IS NULL),
    CHECK (status <> 'active' OR (
        renderer_catalogue_entry_id IS NOT NULL
        AND activated_by IS NOT NULL
        AND activated_at IS NOT NULL
    )),
    CHECK (status <> 'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX local_video_workflows_one_active_idx
ON football_brief.local_video_workflows(provider_key,model_key,workflow_key)
WHERE status='active';

CREATE OR REPLACE FUNCTION football_brief.protect_local_video_workflow()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Local video workflows are immutable and cannot be deleted';
    END IF;
    IF OLD.status='retired' THEN
        RAISE EXCEPTION 'Retired local video workflows are immutable';
    END IF;
    IF OLD.status='active' THEN
        IF NEW.status <> 'retired'
           OR NEW.retired_by IS NULL
           OR NEW.retired_at IS NULL
           OR (to_jsonb(NEW) - ARRAY['status','retired_by','retired_at'])
              IS DISTINCT FROM
              (to_jsonb(OLD) - ARRAY['status','retired_by','retired_at']) THEN
            RAISE EXCEPTION 'Active local video workflows may only be retired without changing lineage';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_workflow_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_workflows
FOR EACH ROW
EXECUTE FUNCTION football_brief.protect_local_video_workflow();

CREATE TABLE football_brief.local_video_executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_job_id uuid NOT NULL REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    generation_attempt_id uuid NOT NULL UNIQUE REFERENCES football_brief.generation_job_attempts(id) ON DELETE RESTRICT,
    local_video_workflow_id uuid NOT NULL REFERENCES football_brief.local_video_workflows(id) ON DELETE RESTRICT,
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    pilot_case_id uuid REFERENCES football_brief.video_pilot_cases(id) ON DELETE RESTRICT,
    input_keyframe_asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    end_frame_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    prompt_sha256 char(64) NOT NULL CHECK (prompt_sha256 ~ '^[0-9a-f]{64}$'),
    negative_prompt_sha256 char(64) NOT NULL CHECK (negative_prompt_sha256 ~ '^[0-9a-f]{64}$'),
    seed bigint NOT NULL,
    width integer NOT NULL CHECK (width BETWEEN 256 AND 8192),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 8192),
    fps integer NOT NULL CHECK (fps BETWEEN 1 AND 120),
    frame_count integer NOT NULL CHECK (frame_count BETWEEN 1 AND 10000),
    inference_steps integer NOT NULL CHECK (inference_steps BETWEEN 1 AND 500),
    status text NOT NULL DEFAULT 'submitted' CHECK (status IN (
        'submitted','running','succeeded','failed','cancelled'
    )),
    provider_request_id text,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    preview_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    wall_clock_ms bigint CHECK (wall_clock_ms IS NULL OR wall_clock_ms >= 0),
    gpu_active_ms bigint CHECK (gpu_active_ms IS NULL OR gpu_active_ms >= 0),
    peak_vram_mib integer CHECK (peak_vram_mib IS NULL OR peak_vram_mib >= 0),
    external_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_cost_usd = 0),
    failure_code text,
    failure_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    CHECK (status <> 'succeeded' OR output_asset_id IS NOT NULL),
    CHECK (status NOT IN ('failed','cancelled') OR completed_at IS NOT NULL)
);

CREATE INDEX local_video_executions_job_idx
ON football_brief.local_video_executions(generation_job_id,submitted_at);

CREATE INDEX local_video_executions_status_idx
ON football_brief.local_video_executions(status,submitted_at);

CREATE OR REPLACE FUNCTION football_brief.protect_terminal_local_video_execution()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Local video executions are immutable and cannot be deleted';
    END IF;
    IF OLD.status IN ('succeeded','failed','cancelled') THEN
        RAISE EXCEPTION 'Terminal local video executions are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_execution_terminal_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_executions
FOR EACH ROW
EXECUTE FUNCTION football_brief.protect_terminal_local_video_execution();

COMMENT ON TABLE football_brief.local_video_workflows IS
    'Versioned, hash-pinned local ComfyUI video workflows bound to renderer and model-use policy evidence.';
COMMENT ON TABLE football_brief.local_video_executions IS
    'Exact zero-fee local video execution lineage for every P87 attempt and canonical MP4 asset.';

COMMIT;
