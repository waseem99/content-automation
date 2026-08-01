-- P126 package-native hybrid scene planning and explainable route selection.
-- Planning may recommend paid routes, but no paid request is executable without
-- an explicit plan approval bound to the active production budget policy.

BEGIN;

CREATE TABLE football_brief.hybrid_routing_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_policy_id uuid REFERENCES football_brief.hybrid_routing_policies(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    default_quality_floor numeric(5,2) NOT NULL DEFAULT 75 CHECK (default_quality_floor BETWEEN 0 AND 100),
    hero_quality_floor numeric(5,2) NOT NULL DEFAULT 86 CHECK (hero_quality_floor BETWEEN 0 AND 100),
    maximum_content_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (maximum_content_cost >= 0),
    maximum_scene_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (maximum_scene_cost >= 0),
    maximum_attempts integer NOT NULL DEFAULT 3 CHECK (maximum_attempts BETWEEN 1 AND 10),
    cloud_requires_local_miss boolean NOT NULL DEFAULT true,
    premium_requires_approval boolean NOT NULL DEFAULT true,
    routing_order text[] NOT NULL DEFAULT ARRAY[
        'reuse_asset','deterministic_composition','local_generation',
        'cloud_portable','premium_low_cost','premium_hero','manual_edit'
    ]::text[],
    scoring_weights jsonb NOT NULL DEFAULT '{
        "route_priority":0.30,"quality":0.25,"acceptance":0.15,
        "cost":0.15,"eta":0.10,"continuity":0.05
    }'::jsonb CHECK (jsonb_typeof(scoring_weights)='object'),
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (brand_id,version),
    CHECK (version=1 OR parent_policy_id IS NOT NULL),
    CHECK (version<>1 OR parent_policy_id IS NULL),
    CHECK (maximum_scene_cost <= maximum_content_cost OR maximum_content_cost=0),
    CHECK (cardinality(routing_order)=7),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX hybrid_routing_policy_one_active_idx
ON football_brief.hybrid_routing_policies(brand_id)
WHERE status='active';

CREATE TABLE football_brief.hybrid_production_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    template_key text NOT NULL CHECK (template_key ~ '^[a-z0-9][a-z0-9._-]{1,119}$'),
    category text NOT NULL CHECK (category IN (
        'intro','outro','caption','background','transition','map','diagram','brand_treatment','reusable_asset'
    )),
    version integer NOT NULL CHECK (version >= 1),
    parent_template_id uuid REFERENCES football_brief.hybrid_production_templates(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    duration_seconds numeric(10,3) CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    quality_rating numeric(5,2) NOT NULL DEFAULT 80 CHECK (quality_rating BETWEEN 0 AND 100),
    supported_formats text[] NOT NULL DEFAULT ARRAY[]::text[],
    supported_territories text[] NOT NULL DEFAULT ARRAY['global']::text[],
    specification jsonb NOT NULL CHECK (jsonb_typeof(specification)='object'),
    specification_sha256 char(64) NOT NULL CHECK (specification_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (brand_id,template_key,category,version),
    CHECK (version=1 OR parent_template_id IS NOT NULL),
    CHECK (version<>1 OR parent_template_id IS NULL),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX hybrid_template_one_active_idx
ON football_brief.hybrid_production_templates(
    COALESCE(brand_id,'00000000-0000-0000-0000-000000000000'::uuid),template_key,category
)
WHERE status='active';

CREATE TABLE football_brief.hybrid_renderer_measurements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_key text NOT NULL CHECK (measurement_key ~ '^[a-z0-9][a-z0-9._-]{1,119}$'),
    version integer NOT NULL CHECK (version >= 1),
    parent_measurement_id uuid REFERENCES football_brief.hybrid_renderer_measurements(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    route_class text NOT NULL CHECK (route_class IN (
        'reuse_asset','deterministic_composition','local_generation',
        'cloud_portable','premium_low_cost','premium_hero','manual_edit'
    )),
    renderer_catalogue_entry_id uuid REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    local_video_workflow_id uuid REFERENCES football_brief.local_video_workflows(id) ON DELETE RESTRICT,
    template_id uuid REFERENCES football_brief.hybrid_production_templates(id) ON DELETE RESTRICT,
    acceptance_rate numeric(7,6) NOT NULL CHECK (acceptance_rate BETWEEN 0 AND 1),
    cost_per_accepted_second numeric(14,6) NOT NULL DEFAULT 0 CHECK (cost_per_accepted_second >= 0),
    queue_eta_p50_seconds integer NOT NULL DEFAULT 0 CHECK (queue_eta_p50_seconds >= 0),
    queue_eta_p95_seconds integer NOT NULL DEFAULT 0 CHECK (queue_eta_p95_seconds >= queue_eta_p50_seconds),
    quality_score numeric(5,2) NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    continuity_risk numeric(5,2) NOT NULL DEFAULT 0 CHECK (continuity_risk BETWEEN 0 AND 100),
    hardware_available boolean NOT NULL DEFAULT true,
    sample_size integer NOT NULL DEFAULT 0 CHECK (sample_size >= 0),
    supported_territories text[] NOT NULL DEFAULT ARRAY['global']::text[],
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence)='object'),
    evidence_digest char(64) NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    observed_at timestamptz NOT NULL,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (measurement_key,version),
    CHECK (version=1 OR parent_measurement_id IS NOT NULL),
    CHECK (version<>1 OR parent_measurement_id IS NULL),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX hybrid_measurement_one_active_idx
ON football_brief.hybrid_renderer_measurements(measurement_key)
WHERE status='active';

CREATE TABLE football_brief.hybrid_route_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pre_generation_package_id uuid NOT NULL REFERENCES football_brief.pre_generation_packages(id) ON DELETE RESTRICT,
    campaign_item_id uuid NOT NULL REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    routing_policy_id uuid NOT NULL REFERENCES football_brief.hybrid_routing_policies(id) ON DELETE RESTRICT,
    budget_policy_id uuid REFERENCES football_brief.production_budget_policies(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_plan_id uuid REFERENCES football_brief.hybrid_route_plans(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'ready' CHECK (status IN (
        'ready','approval_required','blocked','executing','completed','superseded','cancelled'
    )),
    package_sha256 char(64) NOT NULL CHECK (package_sha256 ~ '^[0-9a-f]{64}$'),
    plan_sha256 char(64) NOT NULL CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
    exact_duration_seconds numeric(12,3) NOT NULL CHECK (exact_duration_seconds > 0),
    estimated_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    deadline_at timestamptz NOT NULL,
    route_seconds jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(route_seconds)='object'),
    scoring_snapshot jsonb NOT NULL CHECK (jsonb_typeof(scoring_snapshot)='object'),
    package_snapshot jsonb NOT NULL CHECK (jsonb_typeof(package_snapshot)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    superseded_at timestamptz,
    UNIQUE (pre_generation_package_id,version),
    CHECK (version=1 OR parent_plan_id IS NOT NULL),
    CHECK (version<>1 OR parent_plan_id IS NULL),
    CHECK (status<>'completed' OR completed_at IS NOT NULL),
    CHECK (status<>'superseded' OR superseded_at IS NOT NULL)
);

CREATE UNIQUE INDEX hybrid_route_plan_one_live_idx
ON football_brief.hybrid_route_plans(pre_generation_package_id)
WHERE status IN ('ready','approval_required','blocked','executing');

CREATE TABLE football_brief.hybrid_route_scenes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_plan_id uuid NOT NULL REFERENCES football_brief.hybrid_route_plans(id) ON DELETE RESTRICT,
    shot_id text NOT NULL CHECK (length(btrim(shot_id)) BETWEEN 1 AND 120),
    scene_key text NOT NULL CHECK (length(btrim(scene_key)) BETWEEN 1 AND 120),
    sequence integer NOT NULL CHECK (sequence >= 1),
    start_seconds numeric(12,3) NOT NULL CHECK (start_seconds >= 0),
    end_seconds numeric(12,3) NOT NULL CHECK (end_seconds > start_seconds),
    duration_seconds numeric(12,3) NOT NULL CHECK (duration_seconds > 0),
    render_class text NOT NULL CHECK (render_class IN (
        'reuse_asset','deterministic_composition','local_generation',
        'cloud_portable','premium_low_cost','premium_hero','manual_edit'
    )),
    status text NOT NULL DEFAULT 'planned' CHECK (status IN (
        'planned','approval_required','queued','running','accepted','failed','blocked','cancelled'
    )),
    selected_candidate_id uuid,
    continuity_group text NOT NULL CHECK (length(btrim(continuity_group)) BETWEEN 1 AND 240),
    bindings jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(bindings)='object'),
    keyframe_requirements jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(keyframe_requirements)='object'),
    motion_intensity numeric(5,2) NOT NULL CHECK (motion_intensity BETWEEN 0 AND 100),
    quality_floor numeric(5,2) NOT NULL CHECK (quality_floor BETWEEN 0 AND 100),
    deadline_at timestamptz NOT NULL,
    maximum_attempts integer NOT NULL CHECK (maximum_attempts BETWEEN 1 AND 10),
    maximum_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (maximum_cost >= 0),
    fallback_chain jsonb NOT NULL CHECK (jsonb_typeof(fallback_chain)='array'),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (route_plan_id,shot_id),
    UNIQUE (route_plan_id,sequence),
    CHECK (abs((end_seconds-start_seconds)-duration_seconds) <= 0.001)
);

CREATE TABLE football_brief.hybrid_route_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_scene_id uuid NOT NULL REFERENCES football_brief.hybrid_route_scenes(id) ON DELETE RESTRICT,
    rank integer NOT NULL CHECK (rank >= 1),
    route_class text NOT NULL CHECK (route_class IN (
        'reuse_asset','deterministic_composition','local_generation',
        'cloud_portable','premium_low_cost','premium_hero','manual_edit'
    )),
    renderer_catalogue_entry_id uuid REFERENCES football_brief.renderer_catalogue_entries(id) ON DELETE RESTRICT,
    local_video_workflow_id uuid REFERENCES football_brief.local_video_workflows(id) ON DELETE RESTRICT,
    template_id uuid REFERENCES football_brief.hybrid_production_templates(id) ON DELETE RESTRICT,
    measurement_id uuid REFERENCES football_brief.hybrid_renderer_measurements(id) ON DELETE RESTRICT,
    eligible boolean NOT NULL,
    requires_spend_approval boolean NOT NULL DEFAULT false,
    score numeric(8,4) NOT NULL CHECK (score BETWEEN 0 AND 100),
    estimated_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    expected_eta_seconds integer NOT NULL DEFAULT 0 CHECK (expected_eta_seconds >= 0),
    acceptance_rate numeric(7,6) NOT NULL CHECK (acceptance_rate BETWEEN 0 AND 1),
    quality_score numeric(5,2) NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    continuity_risk numeric(5,2) NOT NULL CHECK (continuity_risk BETWEEN 0 AND 100),
    rejection_reasons jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rejection_reasons)='array'),
    scoring_evidence jsonb NOT NULL CHECK (jsonb_typeof(scoring_evidence)='object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (route_scene_id,rank)
);

ALTER TABLE football_brief.hybrid_route_scenes
    ADD CONSTRAINT hybrid_route_scene_selected_candidate_fk
    FOREIGN KEY (selected_candidate_id)
    REFERENCES football_brief.hybrid_route_candidates(id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX hybrid_route_candidates_scene_idx
ON football_brief.hybrid_route_candidates(route_scene_id,eligible,rank);

CREATE TABLE football_brief.hybrid_spend_approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_plan_id uuid NOT NULL UNIQUE REFERENCES football_brief.hybrid_route_plans(id) ON DELETE RESTRICT,
    budget_policy_id uuid NOT NULL REFERENCES football_brief.production_budget_policies(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('approved','changes_requested','rejected')),
    approved_ceiling numeric(14,6) CHECK (approved_ceiling IS NULL OR approved_ceiling >= 0),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (decision<>'approved' OR approved_ceiling IS NOT NULL)
);

CREATE TABLE football_brief.hybrid_route_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_scene_id uuid NOT NULL REFERENCES football_brief.hybrid_route_scenes(id) ON DELETE RESTRICT,
    candidate_id uuid NOT NULL REFERENCES football_brief.hybrid_route_candidates(id) ON DELETE RESTRICT,
    attempt_number integer NOT NULL CHECK (attempt_number >= 1),
    billing_key text NOT NULL UNIQUE CHECK (length(btrim(billing_key)) BETWEEN 8 AND 240),
    spend_approval_id uuid REFERENCES football_brief.hybrid_spend_approvals(id) ON DELETE RESTRICT,
    generation_job_id uuid UNIQUE REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'planned' CHECK (status IN (
        'planned','queued','running','succeeded','failed','cancelled','accepted','rejected'
    )),
    quoted_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (quoted_cost >= 0),
    actual_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost >= 0),
    rendered_seconds numeric(12,3) NOT NULL DEFAULT 0 CHECK (rendered_seconds >= 0),
    accepted_seconds numeric(12,3) NOT NULL DEFAULT 0 CHECK (accepted_seconds >= 0),
    failure_code text,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (route_scene_id,attempt_number),
    CHECK (actual_cost <= quoted_cost OR quoted_cost=0),
    CHECK (accepted_seconds <= rendered_seconds),
    CHECK (status NOT IN ('succeeded','failed','cancelled','accepted','rejected') OR completed_at IS NOT NULL)
);

CREATE TABLE football_brief.hybrid_route_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_scene_id uuid NOT NULL REFERENCES football_brief.hybrid_route_scenes(id) ON DELETE RESTRICT,
    previous_candidate_id uuid NOT NULL REFERENCES football_brief.hybrid_route_candidates(id) ON DELETE RESTRICT,
    selected_candidate_id uuid NOT NULL REFERENCES football_brief.hybrid_route_candidates(id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 5 AND 5000),
    actor text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (previous_candidate_id <> selected_candidate_id)
);

CREATE TABLE football_brief.hybrid_route_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    route_plan_id uuid NOT NULL REFERENCES football_brief.hybrid_route_plans(id) ON DELETE RESTRICT,
    route_scene_id uuid REFERENCES football_brief.hybrid_route_scenes(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN (
        'plan_created','route_overridden','spend_decision','attempt_created',
        'attempt_completed','fallback_advanced','scene_accepted','plan_completed'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX hybrid_route_events_plan_idx
ON football_brief.hybrid_route_events(route_plan_id,created_at,id);

CREATE OR REPLACE FUNCTION football_brief.protect_hybrid_terminal_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Hybrid routing attempts are immutable and cannot be deleted';
    END IF;
    IF OLD.status IN ('succeeded','failed','cancelled','accepted','rejected') THEN
        RAISE EXCEPTION 'Terminal hybrid routing attempts are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER hybrid_route_attempt_terminal_immutable
BEFORE UPDATE OR DELETE ON football_brief.hybrid_route_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_hybrid_terminal_attempt();

CREATE TRIGGER hybrid_route_scenes_touch_updated_at
BEFORE UPDATE ON football_brief.hybrid_route_scenes
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

COMMENT ON TABLE football_brief.hybrid_route_plans IS
    'Immutable-package route plan with exact EDL, explainable candidates, fallback chains and cost/ETA evidence.';
COMMENT ON TABLE football_brief.hybrid_route_attempts IS
    'Idempotent execution/billing lineage. Paid candidates require a separate approved spend record before queueing.';
COMMENT ON TABLE football_brief.hybrid_renderer_measurements IS
    'Versioned benchmark evidence used for route scoring; no provider is permanently hard-coded as best.';

COMMIT;
