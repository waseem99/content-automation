BEGIN;

CREATE TABLE football_brief.p3_option_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    option_id uuid NOT NULL REFERENCES football_brief.p3_options(id) ON DELETE RESTRICT,
    requirement_id uuid NOT NULL REFERENCES football_brief.p3_requirements(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'returned')),
    reviewed_by text,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (workflow_run_id, option_id)
);

CREATE INDEX p3_option_reviews_workflow_idx ON football_brief.p3_option_reviews (workflow_run_id, status, created_at DESC);
CREATE INDEX p3_option_reviews_option_idx ON football_brief.p3_option_reviews (option_id, created_at DESC);

COMMIT;
