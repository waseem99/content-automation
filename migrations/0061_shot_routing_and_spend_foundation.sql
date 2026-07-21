-- Versioned shot routing, monthly/content budgets, spend decisions, and job reservations.
-- Managed execution remains blocked until exact approved visual, renderer preflight, and spend evidence exist.

BEGIN;

CREATE TABLE football_brief.production_budget_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    month_start date NOT NULL CHECK (month_start=date_trunc('month',month_start)::date),
    version integer NOT NULL CHECK (version>=1),
    parent_policy_id uuid REFERENCES football_brief.production_budget_policies(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired')),
    currency char(3) NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
    monthly_soft_limit numeric(14,6) NOT NULL DEFAULT 0 CHECK (monthly_soft_limit>=0),
    monthly_hard_limit numeric(14,6) NOT NULL CHECK (monthly_hard_limit>=0),
    default_content_limit numeric(14,6) NOT NULL CHECK (default_content_limit>=0),
    approval_threshold numeric(14,6) NOT NULL DEFAULT 0 CHECK (approval_threshold>=0),
    require_approval_for_managed boolean NOT NULL DEFAULT true,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (brand_id,month_start,version),
    CHECK (version=1 OR parent_policy_id IS NOT NULL),
    CHECK (version<>1 OR parent_policy_id IS NULL),
    CHECK (monthly_soft_limit<=monthly_hard_limit),
    CHECK (default_content_limit<=monthly_hard_limit),
    CHECK (approval_threshold<=monthly_hard_limit),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

CREATE UNIQUE INDEX production_budget_one_active_idx
ON football_brief.production_budget_policies(brand_id,month_start)
WHERE status='active';

CREATE TRIGGER production_budget_policies_touch_updated_at
BEFORE UPDATE ON football_brief.production_budget_policies
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.shot_routing_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version>=1),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    budget_policy_id uuid NOT NULL REFERENCES football_brief.production_budget_policies(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version>=1),
    parent_plan_id uuid REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','in_review','approved','changes_requested','rejected','superseded'
    )),
    total_estimated_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (total_estimated_cost>=0),
    managed_shot_count integer NOT NULL DEFAULT 0 CHECK (managed_shot_count>=0),
    local_shot_count integer NOT NULL DEFAULT 0 CHECK (local_shot_count>=0),
    manual_shot_count integer NOT NULL DEFAULT 0 CHECK (manual_shot_count>=0),
    recommendation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(recommendation_snapshot)='object'),
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version>=1),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    decided_at timestamptz,
    UNIQUE (portfolio_content_id,content_version,version),
    UNIQUE (id,portfolio_content_id),
    CHECK (version=1 OR parent_plan_id IS NOT NULL),
    CHECK (version<>1 OR parent_plan_id IS NULL),
    CHECK (status='draft' OR submitted_at IS NOT NULL),
    CHECK (status NOT IN ('approved','changes_requested','rejected') OR decided_at IS NOT NULL)
);

CREATE UNIQUE INDEX shot_routing_one_live_idx
ON football_brief.shot_routing_plans(portfolio_content_id,content_version)
WHERE status IN ('draft','in_review','approved');

CREATE TRIGGER shot_routing_plans_touch_updated_at
BEFORE UPDATE ON football_brief.shot_routing_plans
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.shot_routing_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    routing_plan_id uuid NOT NULL REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    visual_shot_id uuid NOT NULL REFERENCES football_brief.visual_shots(id) ON DELETE RESTRICT,
    selected_candidate_id uuid REFERENCES football_brief.visual_candidates(id) ON DELETE RESTRICT,
    route text NOT NULL CHECK (route IN (
        'deterministic_animation','local_render','managed_render','manual_edit'
    )),
    renderer_preflight_id uuid REFERENCES football_brief.renderer_preflight_records(id) ON DELETE RESTRICT,
    hero_importance numeric(5,2) NOT NULL DEFAULT 0 CHECK (hero_importance BETWEEN 0 AND 100),
    realism_requirement numeric(5,2) NOT NULL DEFAULT 0 CHECK (realism_requirement BETWEEN 0 AND 100),
    motion_complexity numeric(5,2) NOT NULL DEFAULT 0 CHECK (motion_complexity BETWEEN 0 AND 100),
    continuity_requirement numeric(5,2) NOT NULL DEFAULT 0 CHECK (continuity_requirement BETWEEN 0 AND 100),
    factual_control_requirement numeric(5,2) NOT NULL DEFAULT 0 CHECK (factual_control_requirement BETWEEN 0 AND 100),
    local_preview_quality numeric(5,2) NOT NULL DEFAULT 0 CHECK (local_preview_quality BETWEEN 0 AND 100),
    engagement_contribution numeric(5,2) NOT NULL DEFAULT 0 CHECK (engagement_contribution BETWEEN 0 AND 100),
    estimated_cost numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost>=0),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    alternatives jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(alternatives)='array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (routing_plan_id,visual_shot_id),
    UNIQUE (id,routing_plan_id),
    CHECK (
        (route='managed_render' AND renderer_preflight_id IS NOT NULL AND selected_candidate_id IS NOT NULL)
        OR (route<>'managed_render' AND renderer_preflight_id IS NULL)
    ),
    CHECK (route='managed_render' OR estimated_cost=0)
);

CREATE INDEX shot_routing_items_plan_idx
ON football_brief.shot_routing_items(routing_plan_id,route,visual_shot_id);

CREATE TABLE football_brief.production_spend_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    routing_plan_id uuid NOT NULL UNIQUE REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('approved','changes_requested','rejected')),
    approved_ceiling numeric(14,6) CHECK (approved_ceiling IS NULL OR approved_ceiling>=0),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    plan_lock_version bigint NOT NULL CHECK (plan_lock_version>=1),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (decision<>'approved' OR approved_ceiling IS NOT NULL)
);

CREATE TABLE football_brief.production_spend_reservations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    routing_plan_id uuid NOT NULL REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    routing_item_id uuid NOT NULL UNIQUE REFERENCES football_brief.shot_routing_items(id) ON DELETE RESTRICT,
    renderer_preflight_id uuid NOT NULL REFERENCES football_brief.renderer_preflight_records(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version>=1),
    generation_job_id uuid UNIQUE REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    reserved_amount numeric(14,6) NOT NULL CHECK (reserved_amount>=0),
    actual_amount numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_amount>=0),
    overage_amount numeric(14,6) NOT NULL DEFAULT 0 CHECK (overage_amount>=0),
    status text NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved','released','reconciled')),
    soft_limit_exceeded boolean NOT NULL DEFAULT false,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(warnings)='array'),
    reservation_key text NOT NULL UNIQUE CHECK (length(btrim(reservation_key)) BETWEEN 8 AND 240),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    bound_at timestamptz,
    released_at timestamptz,
    reconciled_at timestamptz,
    CHECK (generation_job_id IS NULL OR bound_at IS NOT NULL),
    CHECK (status<>'released' OR released_at IS NOT NULL),
    CHECK (status<>'reconciled' OR reconciled_at IS NOT NULL)
);

CREATE INDEX production_spend_reservations_content_idx
ON football_brief.production_spend_reservations(portfolio_content_id,content_version,status);

CREATE TABLE football_brief.production_spend_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    routing_plan_id uuid NOT NULL REFERENCES football_brief.shot_routing_plans(id) ON DELETE RESTRICT,
    reservation_id uuid REFERENCES football_brief.production_spend_reservations(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'plan_created','plan_submitted','decision_recorded','reservation_created',
        'reservation_bound','reservation_released','reservation_reconciled','route_overridden'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX production_spend_events_plan_idx
ON football_brief.production_spend_events(routing_plan_id,created_at,id);

COMMENT ON TABLE football_brief.shot_routing_plans IS
    'Versioned content routing recommendation over an exact approved visual project and active monthly budget policy.';
COMMENT ON TABLE football_brief.production_spend_reservations IS
    'Pre-job managed-render spend reservations. Active reservations count against both monthly and approved content ceilings.';

COMMIT;
