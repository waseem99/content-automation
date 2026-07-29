-- P114: guarded local ComfyUI video rendering through the existing P87 queue.
-- No model download, paid request, public publishing, or automatic activation occurs here.

BEGIN;

ALTER TABLE football_brief.generation_jobs
    DROP CONSTRAINT generation_jobs_job_type_check;

ALTER TABLE football_brief.generation_jobs
    ADD CONSTRAINT generation_jobs_job_type_check CHECK (job_type IN (
        'concept', 'script', 'narration', 'keyframe', 'preview', 'local_clip',
        'premium_clip', 'assembly', 'caption', 'thumbnail', 'package', 'publishing'
    ));

CREATE TABLE football_brief.local_video_renderer_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key text NOT NULL CHECK (provider_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    model_key text NOT NULL CHECK (model_key ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 200),
    version integer NOT NULL CHECK (version >= 1),
    parent_profile_id uuid REFERENCES football_brief.local_video_renderer_profiles(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','blocked','retired')),
    renderer_catalogue_entry_id uuid NOT NULL
        REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    model_policy_id uuid NOT NULL
        REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    workflow_format text NOT NULL DEFAULT 'comfyui_api' CHECK (workflow_format='comfyui_api'),
    workflow_path text,
    workflow_sha256 char(64) CHECK (workflow_sha256 IS NULL OR workflow_sha256 ~ '^[0-9a-f]{64}$'),
    model_files jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(model_files)='array'),
    default_settings jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(default_settings)='object'),
    activation_evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(activation_evidence)='object'),
    blocked_reason text,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (provider_key, model_key, version),
    CHECK (version = 1 OR parent_profile_id IS NOT NULL),
    CHECK (version <> 1 OR parent_profile_id IS NULL),
    CHECK (
        status <> 'active' OR (
            workflow_path IS NOT NULL
            AND workflow_sha256 IS NOT NULL
            AND jsonb_array_length(model_files) > 0
            AND activated_by IS NOT NULL
            AND activated_at IS NOT NULL
        )
    ),
    CHECK (status <> 'blocked' OR nullif(btrim(blocked_reason), '') IS NOT NULL),
    CHECK (status <> 'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX local_video_renderer_one_active_idx
ON football_brief.local_video_renderer_profiles (provider_key, model_key)
WHERE status='active';

CREATE INDEX local_video_renderer_lookup_idx
ON football_brief.local_video_renderer_profiles (status, provider_key, model_key, version DESC);

CREATE TABLE football_brief.local_video_clip_bindings (
    generation_job_id uuid PRIMARY KEY
        REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    renderer_profile_id uuid NOT NULL
        REFERENCES football_brief.local_video_renderer_profiles(id) ON DELETE RESTRICT,
    input_asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    pilot_case_id uuid REFERENCES football_brief.video_pilot_cases(id) ON DELETE RESTRICT,
    distribution_scope text NOT NULL CHECK (distribution_scope IN ('internal','territory_limited','global_public')),
    release_territories text[] NOT NULL DEFAULT ARRAY[]::text[],
    workflow_sha256 char(64) NOT NULL CHECK (workflow_sha256 ~ '^[0-9a-f]{64}$'),
    model_evidence jsonb NOT NULL CHECK (jsonb_typeof(model_evidence)='object'),
    output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    output_sha256 char(64) CHECK (output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$'),
    completed_at timestamptz,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (output_asset_id IS NULL AND output_sha256 IS NULL AND completed_at IS NULL)
        OR
        (output_asset_id IS NOT NULL AND output_sha256 IS NOT NULL AND completed_at IS NOT NULL)
    )
);

CREATE INDEX local_video_clip_profile_idx
ON football_brief.local_video_clip_bindings (renderer_profile_id, created_at DESC);

CREATE INDEX local_video_clip_pilot_idx
ON football_brief.local_video_clip_bindings (pilot_case_id)
WHERE pilot_case_id IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.protect_local_video_renderer_profile()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Local video renderer profiles cannot be deleted';
    END IF;
    IF OLD.status IN ('active','blocked','retired') THEN
        IF OLD.status='active'
           AND NEW.status='retired'
           AND NEW.retired_by IS NOT NULL
           AND NEW.retired_at IS NOT NULL
           AND NEW.provider_key IS NOT DISTINCT FROM OLD.provider_key
           AND NEW.model_key IS NOT DISTINCT FROM OLD.model_key
           AND NEW.display_name IS NOT DISTINCT FROM OLD.display_name
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_profile_id IS NOT DISTINCT FROM OLD.parent_profile_id
           AND NEW.renderer_catalogue_entry_id IS NOT DISTINCT FROM OLD.renderer_catalogue_entry_id
           AND NEW.model_policy_id IS NOT DISTINCT FROM OLD.model_policy_id
           AND NEW.workflow_format IS NOT DISTINCT FROM OLD.workflow_format
           AND NEW.workflow_path IS NOT DISTINCT FROM OLD.workflow_path
           AND NEW.workflow_sha256 IS NOT DISTINCT FROM OLD.workflow_sha256
           AND NEW.model_files IS NOT DISTINCT FROM OLD.model_files
           AND NEW.default_settings IS NOT DISTINCT FROM OLD.default_settings
           AND NEW.activation_evidence IS NOT DISTINCT FROM OLD.activation_evidence
           AND NEW.blocked_reason IS NOT DISTINCT FROM OLD.blocked_reason
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
           AND NEW.activated_by IS NOT DISTINCT FROM OLD.activated_by
           AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Activated, blocked, and retired local video renderer profiles are immutable; create a child version';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_renderer_profile_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_renderer_profiles
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_local_video_renderer_profile();

CREATE OR REPLACE FUNCTION football_brief.protect_local_video_clip_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Local video clip bindings cannot be deleted';
    END IF;
    IF NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
       OR NEW.renderer_profile_id IS DISTINCT FROM OLD.renderer_profile_id
       OR NEW.input_asset_id IS DISTINCT FROM OLD.input_asset_id
       OR NEW.pilot_case_id IS DISTINCT FROM OLD.pilot_case_id
       OR NEW.distribution_scope IS DISTINCT FROM OLD.distribution_scope
       OR NEW.release_territories IS DISTINCT FROM OLD.release_territories
       OR NEW.workflow_sha256 IS DISTINCT FROM OLD.workflow_sha256
       OR NEW.model_evidence IS DISTINCT FROM OLD.model_evidence
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Local video clip lineage is immutable';
    END IF;
    IF OLD.output_asset_id IS NOT NULL THEN
        RAISE EXCEPTION 'Completed local video clip bindings are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_clip_binding_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_clip_bindings
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_local_video_clip_binding();

COMMENT ON TABLE football_brief.local_video_renderer_profiles IS
    'Versioned, policy-bound local ComfyUI video renderer configurations. Draft or blocked profiles cannot execute.';
COMMENT ON TABLE football_brief.local_video_clip_bindings IS
    'Exact P87 job, renderer profile, input asset, distribution entitlement, model evidence, and output lineage for local clips.';

COMMIT;
