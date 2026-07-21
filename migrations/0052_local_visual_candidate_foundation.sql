-- Versioned local visual prompts, continuity references, retained candidates, and review evidence.
-- Media bytes remain in the canonical asset store. Publication and external fees remain disabled.

BEGIN;

CREATE TABLE football_brief.brand_visual_presets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_profile_id uuid NOT NULL REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    preset_key text NOT NULL CHECK (length(btrim(preset_key)) BETWEEN 1 AND 100),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 200),
    version integer NOT NULL CHECK (version >= 1),
    parent_preset_id uuid REFERENCES football_brief.brand_visual_presets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
    palette jsonb NOT NULL DEFAULT '{}'::jsonb,
    subject_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    environment_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    camera_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    lighting_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    framing_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    negative_prompt text NOT NULL DEFAULT '',
    exclusions jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    UNIQUE (brand_profile_id, preset_key, version),
    UNIQUE (id, brand_profile_id),
    CHECK (version = 1 OR parent_preset_id IS NOT NULL),
    CHECK (version <> 1 OR parent_preset_id IS NULL),
    CHECK (status <> 'active' OR activated_at IS NOT NULL)
);

CREATE UNIQUE INDEX brand_visual_preset_one_active_idx
ON football_brief.brand_visual_presets (brand_profile_id, preset_key)
WHERE status = 'active';

CREATE TRIGGER brand_visual_presets_touch_updated_at
BEFORE UPDATE ON football_brief.brand_visual_presets
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.visual_projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version >= 1),
    script_version_id uuid NOT NULL REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    brand_profile_id uuid NOT NULL REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    visual_preset_id uuid NOT NULL REFERENCES football_brief.brand_visual_presets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'ready_for_review', 'approved', 'changes_requested', 'rejected', 'superseded'
    )),
    provider text NOT NULL DEFAULT 'comfyui-local',
    model_id text NOT NULL,
    candidate_count integer NOT NULL DEFAULT 3 CHECK (candidate_count BETWEEN 3 AND 12),
    external_fee_incurred boolean NOT NULL DEFAULT false,
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version >= 1),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    UNIQUE (portfolio_content_id, script_version_id),
    UNIQUE (id, portfolio_content_id),
    CHECK (provider IN ('comfyui-local', 'comfyui-sdxl-local')),
    CHECK (external_fee_incurred = false),
    CHECK (actual_cost_usd = 0)
);

CREATE UNIQUE INDEX visual_project_one_live_idx
ON football_brief.visual_projects (portfolio_content_id)
WHERE status IN ('working', 'ready_for_review', 'approved');

CREATE TRIGGER visual_projects_touch_updated_at
BEFORE UPDATE ON football_brief.visual_projects
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.visual_continuity_references (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    reference_key text NOT NULL CHECK (length(btrim(reference_key)) BETWEEN 1 AND 100),
    reference_type text NOT NULL CHECK (reference_type IN (
        'subject', 'environment', 'landmark', 'palette', 'lighting', 'framing', 'style'
    )),
    asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    reference_fingerprint char(64) NOT NULL,
    description text NOT NULL CHECK (length(btrim(description)) >= 3),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_project_id, reference_key),
    UNIQUE (id, visual_project_id)
);

CREATE INDEX visual_continuity_references_project_idx
ON football_brief.visual_continuity_references (visual_project_id, reference_type, active);

CREATE TABLE football_brief.visual_shots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    scene_plan_entry_id uuid NOT NULL REFERENCES football_brief.script_scene_plan_entries(id) ON DELETE RESTRICT,
    sequence integer NOT NULL CHECK (sequence >= 1),
    current_version_id uuid NOT NULL,
    selected_candidate_id uuid,
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'candidates_ready', 'selected', 'changes_requested', 'rejected', 'approved'
    )),
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version >= 1),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_project_id, scene_plan_entry_id),
    UNIQUE (visual_project_id, sequence),
    UNIQUE (id, visual_project_id)
);

CREATE TRIGGER visual_shots_touch_updated_at
BEFORE UPDATE ON football_brief.visual_shots
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.visual_shot_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_shot_id uuid NOT NULL REFERENCES football_brief.visual_shots(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_version_id uuid,
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'candidates_ready', 'selected', 'changes_requested', 'rejected', 'superseded'
    )),
    compiled_prompt text NOT NULL CHECK (length(btrim(compiled_prompt)) >= 20),
    negative_prompt text NOT NULL DEFAULT '',
    prompt_components jsonb NOT NULL,
    reference_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,
    width integer NOT NULL CHECK (width BETWEEN 256 AND 4096),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 4096),
    aspect_ratio text NOT NULL,
    candidate_target_count integer NOT NULL DEFAULT 3 CHECK (candidate_target_count BETWEEN 3 AND 12),
    revision_reason text,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    UNIQUE (visual_shot_id, version),
    UNIQUE (id, visual_shot_id),
    CHECK (version = 1 OR parent_version_id IS NOT NULL),
    CHECK (version <> 1 OR parent_version_id IS NULL),
    CHECK (jsonb_typeof(prompt_components) = 'object'),
    CHECK (jsonb_typeof(reference_snapshot) = 'array')
);

ALTER TABLE football_brief.visual_shot_versions
    ADD CONSTRAINT visual_shot_version_parent_fk
    FOREIGN KEY (parent_version_id, visual_shot_id)
    REFERENCES football_brief.visual_shot_versions(id, visual_shot_id)
    ON DELETE RESTRICT;

ALTER TABLE football_brief.visual_shots
    ADD CONSTRAINT visual_shot_current_version_fk
    FOREIGN KEY (current_version_id, id)
    REFERENCES football_brief.visual_shot_versions(id, visual_shot_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX visual_shot_one_live_version_idx
ON football_brief.visual_shot_versions (visual_shot_id)
WHERE status IN ('working', 'candidates_ready');

CREATE TRIGGER visual_shot_versions_touch_updated_at
BEFORE UPDATE ON football_brief.visual_shot_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.visual_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_shot_version_id uuid NOT NULL REFERENCES football_brief.visual_shot_versions(id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal >= 1),
    generation_job_id uuid REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    model_id text NOT NULL,
    seed bigint NOT NULL CHECK (seed >= 0),
    asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'generated', 'selected', 'rejected', 'superseded', 'failed'
    )),
    width integer NOT NULL CHECK (width BETWEEN 256 AND 4096),
    height integer NOT NULL CHECK (height BETWEEN 256 AND 4096),
    mime_type text NOT NULL DEFAULT 'image/png',
    prompt_snapshot text NOT NULL,
    negative_prompt_snapshot text NOT NULL DEFAULT '',
    reference_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    checks_status text NOT NULL DEFAULT 'pending' CHECK (checks_status IN ('pending', 'pass', 'fail')),
    duplicate_candidate_id uuid REFERENCES football_brief.visual_candidates(id) ON DELETE RESTRICT,
    duplicate_similarity numeric(6,5) CHECK (duplicate_similarity IS NULL OR duplicate_similarity BETWEEN 0 AND 1),
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd = 0),
    external_fee_incurred boolean NOT NULL DEFAULT false CHECK (external_fee_incurred = false),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_shot_version_id, ordinal),
    UNIQUE (visual_shot_version_id, seed),
    UNIQUE (generation_job_id),
    UNIQUE (id, visual_shot_version_id),
    CHECK (provider IN ('comfyui-local', 'comfyui-sdxl-local')),
    CHECK (jsonb_typeof(reference_snapshot) = 'array'),
    CHECK (jsonb_typeof(provenance) = 'object'),
    CHECK (status NOT IN ('generated', 'selected', 'rejected', 'superseded') OR asset_id IS NOT NULL)
);

CREATE INDEX visual_candidates_version_idx
ON football_brief.visual_candidates (visual_shot_version_id, ordinal);

CREATE UNIQUE INDEX visual_candidate_one_selected_per_version_idx
ON football_brief.visual_candidates (visual_shot_version_id)
WHERE status = 'selected';

CREATE TRIGGER visual_candidates_touch_updated_at
BEFORE UPDATE ON football_brief.visual_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.visual_candidate_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_candidate_id uuid NOT NULL REFERENCES football_brief.visual_candidates(id) ON DELETE RESTRICT,
    check_type text NOT NULL CHECK (check_type IN (
        'format', 'corruption', 'unwanted_text', 'duplicate', 'prompt_coverage',
        'subject_consistency', 'landmark_consistency', 'lighting_consistency',
        'palette_consistency', 'framing'
    )),
    status text NOT NULL CHECK (status IN ('pass', 'warning', 'fail')),
    score numeric(7,4) CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    checked_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_candidate_id, check_type),
    CHECK (jsonb_typeof(evidence) = 'object')
);

CREATE INDEX visual_candidate_checks_idx
ON football_brief.visual_candidate_checks (visual_candidate_id, status, check_type);

CREATE TABLE football_brief.visual_candidate_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    visual_shot_id uuid NOT NULL,
    visual_shot_version_id uuid NOT NULL,
    visual_candidate_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('selected', 'rejected')),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    shot_lock_version bigint NOT NULL CHECK (shot_lock_version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_candidate_id),
    FOREIGN KEY (visual_shot_id, visual_project_id)
        REFERENCES football_brief.visual_shots(id, visual_project_id) ON DELETE RESTRICT,
    FOREIGN KEY (visual_shot_version_id, visual_shot_id)
        REFERENCES football_brief.visual_shot_versions(id, visual_shot_id) ON DELETE RESTRICT,
    FOREIGN KEY (visual_candidate_id, visual_shot_version_id)
        REFERENCES football_brief.visual_candidates(id, visual_shot_version_id) ON DELETE RESTRICT
);

CREATE TABLE football_brief.visual_shot_review_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    visual_shot_id uuid NOT NULL,
    visual_shot_version_id uuid NOT NULL,
    visual_candidate_id uuid,
    action_type text NOT NULL CHECK (action_type IN (
        'prompt', 'subject', 'environment', 'landmark', 'lighting', 'palette', 'framing', 'artifact', 'general'
    )),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    suggested_value text,
    author_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_by_operator_id text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (visual_shot_id, visual_project_id)
        REFERENCES football_brief.visual_shots(id, visual_project_id) ON DELETE RESTRICT,
    FOREIGN KEY (visual_shot_version_id, visual_shot_id)
        REFERENCES football_brief.visual_shot_versions(id, visual_shot_id) ON DELETE RESTRICT,
    FOREIGN KEY (visual_candidate_id, visual_shot_version_id)
        REFERENCES football_brief.visual_candidates(id, visual_shot_version_id) ON DELETE RESTRICT,
    CHECK (
        (resolved_at IS NULL AND resolved_by_operator_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_operator_id IS NOT NULL)
    )
);

CREATE INDEX visual_shot_review_actions_idx
ON football_brief.visual_shot_review_actions (visual_shot_version_id, resolved_at, created_at);

CREATE TABLE football_brief.visual_project_events (
    id bigserial PRIMARY KEY,
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    visual_shot_id uuid,
    visual_shot_version_id uuid,
    visual_candidate_id uuid,
    event text NOT NULL CHECK (event IN (
        'initialized', 'candidate_enqueued', 'candidate_registered', 'candidate_checked',
        'candidate_selected', 'candidate_rejected', 'review_action_created',
        'review_action_resolved', 'shot_revised', 'project_approved',
        'project_changes_requested', 'project_rejected', 'superseded'
    )),
    actor text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX visual_project_events_idx
ON football_brief.visual_project_events (visual_project_id, created_at, id);

COMMENT ON TABLE football_brief.visual_candidates IS
    'Retained local image candidates with exact prompt, seed, model, references, checks, provenance, and zero-fee evidence.';
COMMENT ON TABLE football_brief.visual_candidate_checks IS
    'Per-candidate technical, prompt-coverage, duplicate, consistency, palette, lighting, landmark, and framing checks.';

COMMIT;