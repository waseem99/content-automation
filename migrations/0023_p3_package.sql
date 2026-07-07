BEGIN;

CREATE TABLE football_brief.p3_plan_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'returned')),
    reviewed_by text,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (workflow_run_id, step_plan_id)
);

CREATE INDEX p3_plan_reviews_workflow_idx ON football_brief.p3_plan_reviews (workflow_run_id, status, created_at DESC);
CREATE INDEX p3_plan_reviews_plan_idx ON football_brief.p3_plan_reviews (step_plan_id, created_at DESC);

CREATE TABLE football_brief.p3_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    package_hash char(64) NOT NULL,
    option_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    scene_map jsonb NOT NULL DEFAULT '[]'::jsonb,
    lineage_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, step_plan_id, package_hash)
);

CREATE INDEX p3_packages_workflow_idx ON football_brief.p3_packages (workflow_run_id, created_at DESC);
CREATE INDEX p3_packages_plan_idx ON football_brief.p3_packages (step_plan_id, created_at DESC);
CREATE INDEX p3_packages_stage_idx ON football_brief.p3_packages (stage_execution_id) WHERE stage_execution_id IS NOT NULL;

COMMIT;
