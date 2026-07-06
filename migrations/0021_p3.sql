BEGIN;

CREATE TABLE football_brief.p3_requirements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    requirement_index integer NOT NULL CHECK (requirement_index > 0),
    scene_number integer,
    item_type text NOT NULL,
    purpose text,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'option_added', 'closed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (step_plan_id, requirement_index)
);

CREATE TABLE football_brief.p3_options (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    requirement_id uuid NOT NULL REFERENCES football_brief.p3_requirements(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    option_hash char(64) NOT NULL,
    reference_type text NOT NULL,
    reference_value text NOT NULL,
    status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'chosen', 'returned')),
    reference_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (requirement_id, option_hash)
);

COMMIT;
