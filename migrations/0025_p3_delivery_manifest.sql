BEGIN;

CREATE TABLE football_brief.p3_delivery_manifests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    package_id uuid NOT NULL REFERENCES football_brief.p3_packages(id) ON DELETE RESTRICT,
    step_plan_id uuid NOT NULL REFERENCES football_brief.step_plans(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    manifest_hash char(64) NOT NULL,
    manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    lineage_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    approval_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    package_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_run_id, package_id, manifest_hash)
);

CREATE INDEX p3_delivery_manifests_workflow_idx ON football_brief.p3_delivery_manifests (workflow_run_id, created_at DESC);
CREATE INDEX p3_delivery_manifests_package_idx ON football_brief.p3_delivery_manifests (package_id, created_at DESC);
CREATE INDEX p3_delivery_manifests_stage_idx ON football_brief.p3_delivery_manifests (stage_execution_id) WHERE stage_execution_id IS NOT NULL;

COMMIT;
