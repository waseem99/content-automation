BEGIN;

CREATE TABLE football_brief.p3_package_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    package_id uuid NOT NULL REFERENCES football_brief.p3_packages(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'returned')),
    reviewed_by text,
    rationale text,
    decision_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (workflow_run_id, package_id)
);

CREATE INDEX p3_package_reviews_workflow_idx ON football_brief.p3_package_reviews (workflow_run_id, status, created_at DESC);
CREATE INDEX p3_package_reviews_package_idx ON football_brief.p3_package_reviews (package_id, created_at DESC);

COMMIT;
