-- Versioned platform profiles, exact release inputs, assembly, QA, playback, and immutable package evidence.

BEGIN;

CREATE TABLE football_brief.platform_render_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_key text NOT NULL CHECK (profile_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
    version integer NOT NULL CHECK (version>=1),
    parent_profile_id uuid REFERENCES football_brief.platform_render_profiles(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 200),
    platform text NOT NULL CHECK (length(btrim(platform)) BETWEEN 2 AND 80),
    width integer NOT NULL CHECK (width BETWEEN 64 AND 16384),
    height integer NOT NULL CHECK (height BETWEEN 64 AND 16384),
    fps numeric(8,3) NOT NULL CHECK (fps>0 AND fps<=240),
    container text NOT NULL,
    video_codec text NOT NULL,
    audio_codec text NOT NULL,
    video_bitrate_kbps integer NOT NULL CHECK (video_bitrate_kbps>0),
    audio_bitrate_kbps integer NOT NULL CHECK (audio_bitrate_kbps>0),
    min_duration_seconds numeric(12,3) NOT NULL CHECK (min_duration_seconds>0),
    max_duration_seconds numeric(12,3) NOT NULL CHECK (max_duration_seconds>=min_duration_seconds),
    safe_area jsonb NOT NULL CHECK (jsonb_typeof(safe_area)='object'),
    captions_required boolean NOT NULL DEFAULT true,
    caption_format text NOT NULL CHECK (caption_format IN ('burned_in','sidecar','either')),
    watermark_policy text NOT NULL CHECK (watermark_policy IN ('forbidden','required','optional')),
    disclosure_required boolean NOT NULL DEFAULT false,
    target_loudness_lufs numeric(6,2) NOT NULL CHECK (target_loudness_lufs BETWEEN -60 AND 0),
    loudness_tolerance_lu numeric(6,2) NOT NULL CHECK (loudness_tolerance_lu>0),
    max_true_peak_dbfs numeric(6,2) NOT NULL CHECK (max_true_peak_dbfs BETWEEN -20 AND 0),
    max_av_sync_offset_ms integer NOT NULL CHECK (max_av_sync_offset_ms BETWEEN 0 AND 5000),
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (profile_key,version),
    CHECK (version=1 OR parent_profile_id IS NOT NULL),
    CHECK (version<>1 OR parent_profile_id IS NULL),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX platform_render_profile_one_active_idx
ON football_brief.platform_render_profiles(profile_key)
WHERE status='active';

CREATE TABLE football_brief.final_release_input_approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_version_id uuid NOT NULL
        REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    role text NOT NULL CHECK (role IN (
        'narration','visual_shot','graphic','captions','music','branding','platform_metadata','disclosure'
    )),
    decision text NOT NULL CHECK (decision IN ('approved','rejected')),
    reviewer_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX final_release_input_approvals_lookup_idx
ON football_brief.final_release_input_approvals(artifact_version_id,role,created_at DESC,id DESC);

CREATE TABLE football_brief.final_releases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version>=1),
    version integer NOT NULL CHECK (version>=1),
    parent_release_id uuid REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    render_profile_id uuid NOT NULL
        REFERENCES football_brief.platform_render_profiles(id) ON DELETE RESTRICT,
    routing_plan_id uuid REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    assembly_job_id uuid UNIQUE REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    output_artifact_version_id uuid UNIQUE
        REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','assembly_queued','assembled','qa_complete','in_review',
        'approved','changes_requested','rejected','superseded'
    )),
    input_hash char(64) NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    release_manifest jsonb,
    manifest_hash char(64),
    total_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (total_cost_usd>=0),
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version>=1),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    submitted_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    approved_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    assembly_queued_at timestamptz,
    assembled_at timestamptz,
    qa_completed_at timestamptz,
    submitted_at timestamptz,
    approved_at timestamptz,
    superseded_at timestamptz,
    UNIQUE (portfolio_content_id,content_version,version),
    UNIQUE (id,portfolio_content_id),
    CHECK (version=1 OR parent_release_id IS NOT NULL),
    CHECK (version<>1 OR parent_release_id IS NULL),
    CHECK ((release_manifest IS NULL AND manifest_hash IS NULL) OR (release_manifest IS NOT NULL AND manifest_hash IS NOT NULL)),
    CHECK (status<>'assembly_queued' OR (assembly_job_id IS NOT NULL AND assembly_queued_at IS NOT NULL)),
    CHECK (status NOT IN ('assembled','qa_complete','in_review','approved','changes_requested','rejected','superseded')
           OR (assembly_job_id IS NOT NULL AND output_artifact_version_id IS NOT NULL AND assembled_at IS NOT NULL)),
    CHECK (status NOT IN ('qa_complete','in_review','approved','changes_requested','rejected','superseded') OR qa_completed_at IS NOT NULL),
    CHECK (status NOT IN ('in_review','approved','changes_requested','rejected','superseded') OR submitted_at IS NOT NULL),
    CHECK (status<>'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND release_manifest IS NOT NULL)),
    CHECK (status<>'superseded' OR superseded_at IS NOT NULL)
);

CREATE INDEX final_releases_content_idx
ON football_brief.final_releases(portfolio_content_id,content_version,version DESC);
CREATE UNIQUE INDEX final_release_one_open_version_idx
ON football_brief.final_releases(portfolio_content_id,content_version)
WHERE status IN ('draft','assembly_queued','assembled','qa_complete','in_review');

CREATE TRIGGER final_releases_touch_updated_at
BEFORE UPDATE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.final_release_inputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    artifact_version_id uuid NOT NULL
        REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    approval_id uuid NOT NULL
        REFERENCES football_brief.final_release_input_approvals(id) ON DELETE RESTRICT,
    role text NOT NULL CHECK (role IN (
        'narration','visual_shot','graphic','captions','music','branding','platform_metadata','disclosure'
    )),
    sequence_number integer NOT NULL DEFAULT 0 CHECK (sequence_number>=0),
    required boolean NOT NULL DEFAULT true,
    canonical_asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    asset_sha256 char(64) NOT NULL CHECK (asset_sha256 ~ '^[0-9a-f]{64}$'),
    artifact_snapshot jsonb NOT NULL CHECK (jsonb_typeof(artifact_snapshot)='object'),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (release_id,role,sequence_number,artifact_version_id)
);

CREATE INDEX final_release_inputs_release_idx
ON football_brief.final_release_inputs(release_id,role,sequence_number,id);

CREATE TABLE football_brief.final_release_qa_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    output_artifact_version_id uuid NOT NULL
        REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    profile_id uuid NOT NULL REFERENCES football_brief.platform_render_profiles(id) ON DELETE RESTRICT,
    outcome text NOT NULL CHECK (outcome IN ('pass','block')),
    checks jsonb NOT NULL CHECK (jsonb_typeof(checks)='array'),
    blocking_failures jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(blocking_failures)='array'),
    inspection jsonb NOT NULL CHECK (jsonb_typeof(inspection)='object'),
    input_hash char(64) NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    output_hash char(64) NOT NULL CHECK (output_hash ~ '^[0-9a-f]{64}$'),
    report_hash char(64) NOT NULL UNIQUE CHECK (report_hash ~ '^[0-9a-f]{64}$'),
    inspector_label text NOT NULL CHECK (length(btrim(inspector_label)) BETWEEN 2 AND 200),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (outcome<>'block' OR jsonb_array_length(blocking_failures)>0),
    CHECK (outcome<>'pass' OR jsonb_array_length(blocking_failures)=0)
);

CREATE INDEX final_release_qa_reports_release_idx
ON football_brief.final_release_qa_reports(release_id,created_at DESC,id DESC);

CREATE TABLE football_brief.final_release_playback_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('approved','changes_requested','rejected')),
    checklist jsonb NOT NULL CHECK (jsonb_typeof(checklist)='object'),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    reviewer_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    release_lock_version bigint NOT NULL CHECK (release_lock_version>=1),
    review_hash char(64) NOT NULL UNIQUE CHECK (review_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX final_release_playback_reviews_release_idx
ON football_brief.final_release_playback_reviews(release_id,created_at DESC,id DESC);

CREATE TABLE football_brief.final_release_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'created','assembly_queued','assembly_completed','qa_recorded','submitted',
        'playback_reviewed','approved','changes_requested','rejected','superseded'
    )),
    actor text NOT NULL,
    from_lock_version bigint,
    to_lock_version bigint NOT NULL CHECK (to_lock_version>=1),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX final_release_events_release_idx
ON football_brief.final_release_events(release_id,created_at,id);

COMMENT ON TABLE football_brief.final_releases IS
    'Versioned final assembly and package state. Approved releases retain exact artifact, profile, QA, cost, and review evidence.';
COMMENT ON TABLE football_brief.final_release_qa_reports IS
    'Immutable deterministic technical QA evidence for one exact assembled output and platform profile.';

COMMIT;
