BEGIN;

CREATE TABLE football_brief.resource_requirements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    requirement_index integer NOT NULL CHECK (requirement_index > 0),
    scene_number integer,
    requirement_type text NOT NULL,
    purpose text,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'candidate_added', 'closed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (step_plan_id, requirement_index)
);

CREATE INDEX resource_requirements_workflow_idx ON football_brief.resource_requirements (workflow_run_id, created_at DESC);
CREATE INDEX resource_requirements_plan_idx ON football_brief.resource_requirements (step_plan_id, requirement_index);

CREATE TABLE football_brief.resource_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    requirement_id uuid NOT NULL REFERENCES football_brief.resource_requirements(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    candidate_hash char(64) NOT NULL,
    source_type text NOT NULL,
    source_ref text NOT NULL,
    status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'selected', 'returned')),
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    operator_notes text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (requirement_id, candidate_hash)
);

CREATE INDEX resource_candidates_workflow_idx ON football_brief.resource_candidates (workflow_run_id, created_at DESC);
CREATE INDEX resource_candidates_requirement_idx ON football_brief.resource_candidates (requirement_id, created_at DESC);
CREATE INDEX resource_candidates_plan_idx ON football_brief.resource_candidates (step_plan_id, created_at DESC);

COMMIT;
