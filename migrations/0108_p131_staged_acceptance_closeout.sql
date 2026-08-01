-- P131 retained cross-workstream closeout evidence.
-- The report distinguishes proven database/control-plane capacity from real
-- renderer throughput that remains separately unproven.

BEGIN;

CREATE TABLE football_brief.staged_acceptance_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_key text NOT NULL UNIQUE CHECK (report_key ~ '^[a-z0-9][a-z0-9._-]{7,159}$'),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','passed','failed')),
    central_ecosystem_verdict text NOT NULL CHECK (central_ecosystem_verdict IN (
        'proven','not_proven'
    )),
    monthly_renderer_verdict text NOT NULL CHECK (monthly_renderer_verdict IN (
        'proven','proven_with_specified_infrastructure','not_yet_proven'
    )),
    control_plane_items integer NOT NULL CHECK (control_plane_items>=0),
    control_plane_checks bigint NOT NULL CHECK (control_plane_checks>=0),
    dag_tasks bigint NOT NULL CHECK (dag_tasks>=0),
    dag_workers integer NOT NULL CHECK (dag_workers>=0),
    autopilot_items integer NOT NULL CHECK (autopilot_items>=0),
    autopilot_ready integer NOT NULL CHECK (autopilot_ready>=0),
    grouped_hard_blocks integer NOT NULL CHECK (grouped_hard_blocks>=0),
    storage_assets integer NOT NULL CHECK (storage_assets>=0),
    storage_locations integer NOT NULL CHECK (storage_locations>=0),
    mass_operation_items integer NOT NULL CHECK (mass_operation_items>=0),
    hybrid_master_seconds numeric(12,3) NOT NULL CHECK (hybrid_master_seconds>=0),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    proven_capabilities jsonb NOT NULL CHECK (jsonb_typeof(proven_capabilities)='array'),
    unresolved_renderer_measurements jsonb NOT NULL CHECK (jsonb_typeof(unresolved_renderer_measurements)='array'),
    management_summary jsonb NOT NULL CHECK (jsonb_typeof(management_summary)='object'),
    report_sha256 char(64) NOT NULL CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (status='draft' OR completed_at IS NOT NULL),
    CHECK (status<>'passed' OR (
        central_ecosystem_verdict='proven'
        AND control_plane_items>=10000
        AND control_plane_checks>=1000000
        AND dag_tasks>=1000000
        AND dag_workers>=100
        AND autopilot_items>=1000
        AND autopilot_ready>=950
        AND storage_locations>=100000
        AND mass_operation_items>=1000
        AND hybrid_master_seconds>=120
        AND jsonb_array_length(proven_capabilities)>0
    )),
    CHECK (
        monthly_renderer_verdict<>'not_yet_proven'
        OR jsonb_array_length(unresolved_renderer_measurements)>0
    )
);

CREATE OR REPLACE FUNCTION football_brief.protect_staged_acceptance_report()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Staged acceptance reports are immutable';
    END IF;
    IF OLD.status<>'draft' THEN
        RAISE EXCEPTION 'Completed staged acceptance reports are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER staged_acceptance_report_immutable
BEFORE UPDATE OR DELETE ON football_brief.staged_acceptance_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_staged_acceptance_report();

COMMENT ON TABLE football_brief.staged_acceptance_reports IS
    'Versioned management closeout over measured GitHub workflow evidence; never upgrades database benchmarks into renderer-throughput claims.';

COMMIT;
