-- P114 immutable local-video workflow manifests and model acknowledgements.
-- No model download or generation is activated by this migration.

BEGIN;

CREATE TABLE football_brief.local_video_model_acknowledgements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key text NOT NULL,
    model_key text NOT NULL,
    checkpoint_sha256 char(64) NOT NULL CHECK (checkpoint_sha256 ~ '^[0-9a-f]{64}$'),
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    local_path_hint text NOT NULL CHECK (length(btrim(local_path_hint)) BETWEEN 1 AND 2000),
    license_acknowledged boolean NOT NULL DEFAULT false,
    acknowledged_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    acknowledged_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    UNIQUE (provider_key, model_key, checkpoint_sha256)
);

CREATE TABLE football_brief.local_video_workflow_manifests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_key text NOT NULL CHECK (workflow_key ~ '^[a-z0-9][a-z0-9._-]{1,199}$'),
    version integer NOT NULL CHECK (version >= 1),
    parent_manifest_id uuid REFERENCES football_brief.local_video_workflow_manifests(id) ON DELETE RESTRICT,
    renderer_catalogue_entry_id uuid NOT NULL REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    model_acknowledgement_id uuid NOT NULL REFERENCES football_brief.local_video_model_acknowledgements(id) ON DELETE RESTRICT,
    operation text NOT NULL CHECK (operation IN ('image_to_video','text_to_video','video_to_video','video_edit')),
    profile_key text NOT NULL CHECK (profile_key IN ('draft','selected_final','transition','start_end_frame','upscale')),
    workflow_path text NOT NULL CHECK (length(btrim(workflow_path)) BETWEEN 1 AND 2000),
    workflow_sha256 char(64) NOT NULL CHECK (workflow_sha256 ~ '^[0-9a-f]{64}$'),
    expected_checkpoint_sha256 char(64) NOT NULL CHECK (expected_checkpoint_sha256 ~ '^[0-9a-f]{64}$'),
    supported_widths integer[] NOT NULL DEFAULT ARRAY[]::integer[],
    supported_heights integer[] NOT NULL DEFAULT ARRAY[]::integer[],
    supported_fps integer[] NOT NULL DEFAULT ARRAY[24]::integer[],
    min_frames integer NOT NULL CHECK (min_frames >= 1),
    max_frames integer NOT NULL CHECK (max_frames >= min_frames),
    min_steps integer NOT NULL CHECK (min_steps >= 1),
    max_steps integer NOT NULL CHECK (max_steps >= min_steps),
    required_input_kinds text[] NOT NULL DEFAULT ARRAY[]::text[],
    parameter_schema jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(parameter_schema)='object'),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (workflow_key, version),
    CHECK (version = 1 OR parent_manifest_id IS NOT NULL),
    CHECK (version <> 1 OR parent_manifest_id IS NULL),
    CHECK (status <> 'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status <> 'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX local_video_workflow_one_active_idx
ON football_brief.local_video_workflow_manifests (workflow_key)
WHERE status='active';

CREATE TABLE football_brief.local_video_renderer_preflights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version >= 1),
    pilot_case_id uuid REFERENCES football_brief.video_pilot_cases(id) ON DELETE RESTRICT,
    workflow_manifest_id uuid NOT NULL REFERENCES football_brief.local_video_workflow_manifests(id) ON DELETE RESTRICT,
    model_policy_id uuid NOT NULL REFERENCES football_brief.video_model_use_policies(id) ON DELETE RESTRICT,
    request_fingerprint char(64) NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    distribution_scope text NOT NULL CHECK (distribution_scope IN ('internal','territory_limited','global_public')),
    release_territories text[] NOT NULL DEFAULT ARRAY[]::text[],
    width integer NOT NULL CHECK (width BETWEEN 256 AND 8192),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 8192),
    fps integer NOT NULL CHECK (fps BETWEEN 1 AND 240),
    frame_count integer NOT NULL CHECK (frame_count BETWEEN 1 AND 10000),
    inference_steps integer NOT NULL CHECK (inference_steps BETWEEN 1 AND 500),
    accepted boolean NOT NULL,
    rejection_reasons jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rejection_reasons)='array'),
    external_fee_possible boolean NOT NULL DEFAULT false,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_content_id, content_version, request_fingerprint),
    CHECK (accepted OR jsonb_array_length(rejection_reasons) > 0),
    CHECK (external_fee_possible = false)
);

COMMENT ON TABLE football_brief.local_video_workflow_manifests IS
    'Immutable workflow identity and bounded generation parameters for local ComfyUI video rendering.';
COMMENT ON TABLE football_brief.local_video_renderer_preflights IS
    'Append-only fail-closed evidence created before any local video generation job is submitted.';

COMMIT;
