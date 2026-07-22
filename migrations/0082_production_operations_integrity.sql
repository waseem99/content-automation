-- Fail-closed release, backup, drill, alert, and restore evidence transitions.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_operations_release()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    previous_row football_brief.operations_releases%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Operations release evidence cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.previous_release_id IS NOT NULL THEN
            SELECT * INTO previous_row
              FROM football_brief.operations_releases
             WHERE id=NEW.previous_release_id;
            IF previous_row.id IS NULL
               OR previous_row.environment IS DISTINCT FROM NEW.environment
               OR previous_row.status NOT IN ('healthy','failed','rolled_back','retired') THEN
                RAISE EXCEPTION 'Release lineage requires a terminal previous release in the same environment';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.release_key IS DISTINCT FROM OLD.release_key
       OR NEW.git_sha IS DISTINCT FROM OLD.git_sha
       OR NEW.image_digest IS DISTINCT FROM OLD.image_digest
       OR NEW.configuration_digest IS DISTINCT FROM OLD.configuration_digest
       OR NEW.migration_head IS DISTINCT FROM OLD.migration_head
       OR NEW.previous_release_id IS DISTINCT FROM OLD.previous_release_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Operations release identity is immutable';
    END IF;
    IF OLD.status IN ('rolled_back','retired') THEN
        RAISE EXCEPTION 'Terminal operations release evidence is immutable';
    END IF;
    IF OLD.status='planned' AND NEW.status='deploying' AND NEW.deploying_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status='deploying' AND NEW.status='healthy' AND NEW.healthy_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('planned','deploying') AND NEW.status='failed' AND NEW.failed_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('healthy','failed') AND NEW.status='rolled_back' AND NEW.rolled_back_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('healthy','failed') AND NEW.status='retired' AND NEW.retired_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid operations release transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER operations_releases_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.operations_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_operations_release();

CREATE OR REPLACE FUNCTION football_brief.validate_operations_backup_set()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Operations backup evidence cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.database_object_ref ~* '(password|secret|token|api[_-]?key)='
           OR NEW.artifact_object_ref ~* '(password|secret|token|api[_-]?key)=' THEN
            RAISE EXCEPTION 'Backup object references cannot contain secret material';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.backup_key IS DISTINCT FROM OLD.backup_key
       OR NEW.database_object_ref IS DISTINCT FROM OLD.database_object_ref
       OR NEW.artifact_object_ref IS DISTINCT FROM OLD.artifact_object_ref
       OR NEW.database_sha256 IS DISTINCT FROM OLD.database_sha256
       OR NEW.artifact_sha256 IS DISTINCT FROM OLD.artifact_sha256
       OR NEW.migration_head IS DISTINCT FROM OLD.migration_head
       OR NEW.database_bytes IS DISTINCT FROM OLD.database_bytes
       OR NEW.artifact_bytes IS DISTINCT FROM OLD.artifact_bytes
       OR NEW.retention_until IS DISTINCT FROM OLD.retention_until
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Operations backup identity and checksums are immutable';
    END IF;
    IF OLD.status='available' AND NEW.status='restored' AND NEW.restored_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('available','restored') AND NEW.status='expired' AND NEW.expired_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid operations backup transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER operations_backup_sets_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.operations_backup_sets
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_operations_backup_set();

CREATE OR REPLACE FUNCTION football_brief.validate_operations_drill()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Operations drill evidence cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.status<>'running' OR NEW.completed_at IS NOT NULL OR NEW.evidence_digest IS NOT NULL THEN
            RAISE EXCEPTION 'Operations drills must begin in running state';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status<>'running' THEN
        RAISE EXCEPTION 'Terminal operations drill evidence is immutable';
    END IF;
    IF NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.drill_kind IS DISTINCT FROM OLD.drill_kind
       OR NEW.release_id IS DISTINCT FROM OLD.release_id
       OR NEW.backup_set_id IS DISTINCT FROM OLD.backup_set_id
       OR NEW.started_by IS DISTINCT FROM OLD.started_by
       OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'Operations drill identity is immutable';
    END IF;
    IF NEW.status IN ('passed','failed')
       AND NEW.completed_at IS NOT NULL
       AND NEW.evidence_digest IS NOT NULL
       AND NEW.evidence<>'{}'::jsonb THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Operations drill completion requires terminal status and evidence';
END;
$$;

CREATE TRIGGER operations_drill_runs_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.operations_drill_runs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_operations_drill();

CREATE OR REPLACE FUNCTION football_brief.validate_operations_alert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Operations alert evidence cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.status<>'open' OR NEW.details='{}'::jsonb THEN
            RAISE EXCEPTION 'Operations alerts must begin open with details';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.alert_key IS DISTINCT FROM OLD.alert_key
       OR NEW.alert_kind IS DISTINCT FROM OLD.alert_kind
       OR NEW.severity IS DISTINCT FROM OLD.severity
       OR NEW.source IS DISTINCT FROM OLD.source
       OR NEW.details IS DISTINCT FROM OLD.details
       OR NEW.details_digest IS DISTINCT FROM OLD.details_digest
       OR NEW.detected_at IS DISTINCT FROM OLD.detected_at THEN
        RAISE EXCEPTION 'Operations alert identity and detection evidence are immutable';
    END IF;
    IF OLD.status='open' AND NEW.status='acknowledged'
       AND NEW.acknowledged_by IS NOT NULL AND NEW.acknowledged_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('open','acknowledged') AND NEW.status='resolved'
       AND NEW.resolved_by IS NOT NULL AND NEW.resolved_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid operations alert transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER operations_alert_events_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.operations_alert_events
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_operations_alert();

CREATE OR REPLACE FUNCTION football_brief.validate_operations_restore_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    backup_row football_brief.operations_backup_sets%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'Operations restore evidence is append-only';
    END IF;
    SELECT * INTO backup_row
      FROM football_brief.operations_backup_sets
     WHERE id=NEW.backup_set_id;
    IF backup_row.id IS NULL
       OR backup_row.environment IS DISTINCT FROM NEW.environment
       OR backup_row.status NOT IN ('available','restored')
       OR NEW.verification='{}'::jsonb THEN
        RAISE EXCEPTION 'Restore evidence requires the exact available backup and verification details';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER operations_restore_events_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.operations_restore_events
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_operations_restore_event();

COMMIT;
