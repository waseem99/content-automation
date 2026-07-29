-- P114 local zero-fee video renderer identity, workflow lineage and P87 binding.

BEGIN;

ALTER TABLE football_brief.generation_jobs
    DROP CONSTRAINT generation_jobs_job_type_check;
ALTER TABLE football_brief.generation_jobs
    ADD CONSTRAINT generation_jobs_job_type_check CHECK (job_type IN (
        'concept','script','narration','keyframe','preview','local_clip','premium_clip',
        'assembly','caption','thumbnail','package','publishing'
    ));

CREATE TABLE football_brief.local_video_workflow_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_key text NOT NULL CHECK (workflow_key ~ '^[a-z0-9][a-z0-9._-]{1,119}$'),
    version integer NOT NULL CHECK (version >= 1),
    parent_workflow_id uuid REFERENCES football_brief.local_video_workflow_versions(id) ON DELETE RESTRICT,
    provider_key text NOT NULL,
    model_key text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('image_to_video','start_end_frame','video_upscale')),
    profile text NOT NULL CHECK (profile IN ('draft','selected_final','transition','upscale')),
    workflow_relative_path text NOT NULL CHECK (length(btrim(workflow_relative_path)) BETWEEN 3 AND 1000),
    workflow_sha256 char(64) NOT NULL CHECK (workflow_sha256 ~ '^[0-9a-f]{64}$'),
    checkpoint_sha256 char(64) NOT NULL CHECK (checkpoint_sha256 ~ '^[0-9a-f]{64}$'),
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    parameter_contract jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(parameter_contract)='object'),
    output_contract jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(output_contract)='object'),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (workflow_key, version),
    CHECK (version = 1 OR parent_workflow_id IS NOT NULL),
    CHECK (version <> 1 OR parent_workflow_id IS NULL),
    CHECK (status <> 'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status <> 'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX local_video_workflow_one_active_idx
ON football_brief.local_video_workflow_versions(workflow_key)
WHERE status='active';

CREATE TABLE football_brief.local_video_job_bindings (
    generation_job_id uuid PRIMARY KEY REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL REFERENCES football_brief.local_video_workflow_versions(id) ON DELETE RESTRICT,
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    source_asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    end_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    request_fingerprint char(64) NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    prompt_snapshot text NOT NULL CHECK (length(btrim(prompt_snapshot)) BETWEEN 3 AND 10000),
    negative_prompt_snapshot text,
    seed bigint NOT NULL,
    width integer NOT NULL CHECK (width BETWEEN 256 AND 4096),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 4096),
    fps integer NOT NULL CHECK (fps BETWEEN 1 AND 60),
    frame_count integer NOT NULL CHECK (frame_count BETWEEN 1 AND 1000),
    inference_steps integer NOT NULL CHECK (inference_steps BETWEEN 1 AND 200),
    output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    preview_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    external_fee_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_fee_usd = 0),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (request_fingerprint),
    CHECK (end_asset_id IS NULL OR end_asset_id <> source_asset_id),
    CHECK (output_asset_id IS NULL OR completed_at IS NOT NULL)
);

CREATE OR REPLACE FUNCTION football_brief.protect_local_video_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Local video lineage cannot be deleted'; END IF;
    IF OLD.status IN ('active','retired') AND TG_TABLE_NAME='local_video_workflow_versions' THEN
        IF NEW.status='retired' AND OLD.status='active' AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Active or retired local video workflows are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_workflow_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_workflow_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_local_video_identity();

CREATE OR REPLACE FUNCTION football_brief.protect_local_video_binding()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Local video job bindings cannot be deleted'; END IF;
    IF NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
       OR NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id
       OR NEW.model_policy_id IS DISTINCT FROM OLD.model_policy_id
       OR NEW.source_asset_id IS DISTINCT FROM OLD.source_asset_id
       OR NEW.end_asset_id IS DISTINCT FROM OLD.end_asset_id
       OR NEW.request_fingerprint IS DISTINCT FROM OLD.request_fingerprint
       OR NEW.prompt_snapshot IS DISTINCT FROM OLD.prompt_snapshot
       OR NEW.negative_prompt_snapshot IS DISTINCT FROM OLD.negative_prompt_snapshot
       OR NEW.seed IS DISTINCT FROM OLD.seed
       OR NEW.width IS DISTINCT FROM OLD.width
       OR NEW.height IS DISTINCT FROM OLD.height
       OR NEW.fps IS DISTINCT FROM OLD.fps
       OR NEW.frame_count IS DISTINCT FROM OLD.frame_count
       OR NEW.inference_steps IS DISTINCT FROM OLD.inference_steps
       OR NEW.external_fee_usd IS DISTINCT FROM OLD.external_fee_usd
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Local video request identity is immutable';
    END IF;
    IF OLD.output_asset_id IS NOT NULL THEN
        RAISE EXCEPTION 'Completed local video bindings are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_binding_immutable
BEFORE UPDATE OR DELETE ON football_brief.local_video_job_bindings
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_local_video_binding();

COMMIT;
