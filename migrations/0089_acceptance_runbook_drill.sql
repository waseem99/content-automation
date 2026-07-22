-- Add an explicit, upgrade-safe P100 runbook validation drill to the merged P99 operations evidence model.

BEGIN;

ALTER TABLE football_brief.operations_drill_runs
    DROP CONSTRAINT operations_drill_runs_drill_kind_check,
    ADD CONSTRAINT operations_drill_runs_drill_kind_check CHECK (drill_kind IN (
        'staging_recreate','database_restore','artifact_restore','worker_restart',
        'release_rollback','api_health_alert','queue_stall_alert','worker_failure_alert',
        'low_storage_alert','security_scan','runbook_validation'
    ));

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_runbook_drill()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.drill_kind<>'runbook_validation' THEN
        RETURN NEW;
    END IF;
    IF NEW.environment<>'staging' OR NEW.release_id IS NOT NULL OR NEW.backup_set_id IS NOT NULL THEN
        RAISE EXCEPTION 'Runbook validation is a standalone staging drill';
    END IF;
    IF NEW.status='passed' THEN
        IF NEW.evidence->>'runbook_path' IS DISTINCT FROM 'docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md'
           OR COALESCE(NEW.evidence->>'runbook_sha256','') !~ '^[0-9a-f]{64}$'
           OR NEW.evidence->>'operator_profile' IS DISTINCT FROM 'non_developer'
           OR COALESCE(NEW.evidence->>'checklist_completed','false')<>'true'
           OR nullif(btrim(COALESCE(NEW.evidence->>'completed_by','')),'') IS NULL THEN
            RAISE EXCEPTION 'Passed runbook validation requires exact path, digest, non-developer profile, completed checklist, and operator evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER operations_drill_runs_runbook_valid
BEFORE INSERT OR UPDATE ON football_brief.operations_drill_runs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_runbook_drill();

COMMENT ON FUNCTION football_brief.validate_acceptance_runbook_drill() IS
    'Validates explicit non-developer execution evidence for the packaged P100 acceptance runbook.';

COMMIT;
