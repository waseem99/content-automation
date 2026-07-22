-- Require evidence-backed item pass, per-brand local/managed coverage, and operations evidence before sign-off.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_item_pass()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    missing_count integer;
BEGIN
    IF NEW.status='passed' AND OLD.status IS DISTINCT FROM 'passed' THEN
        WITH required(category) AS (
            VALUES
              ('brand_profile'),('narration_preset'),('role_assignment'),('concept_approval'),
              ('source_evidence'),('script_approval'),('script_revision'),('narration_approval'),
              ('narration_revision'),('visual_approval'),('visual_revision'),('routing_explanation'),
              ('spend_approval'),('renderer_lineage'),('artifact_lineage'),('final_qa'),
              ('release_manifest'),('publisher_decision'),('staging_delivery'),
              ('analytics_observation'),('production_economics')
        )
        SELECT count(*) INTO missing_count
          FROM required r
         WHERE NOT EXISTS (
             SELECT 1 FROM football_brief.acceptance_pilot_evidence ape
              WHERE ape.pilot_item_id=NEW.id AND ape.category=r.category AND ape.passed
         );
        IF missing_count<>0 OR NEW.staging_delivery_request_id IS NULL THEN
            RAISE EXCEPTION 'Pilot item pass requires all content evidence and exact staging delivery';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_item_pass_evidence
BEFORE UPDATE ON football_brief.acceptance_pilot_items
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_item_pass();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_evidence_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    valid_operator boolean;
    subject_uuid uuid;
    valid_subject boolean:=false;
BEGIN
    IF NEW.passed AND NEW.subject_id LIKE 'missing:%' THEN
        RAISE EXCEPTION 'Passed acceptance evidence must bind an existing exact subject';
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.observed_by AND ou.active AND our.role IN ('admin','reviewer')
    ) INTO valid_operator;
    IF NOT valid_operator THEN
        RAISE EXCEPTION 'Acceptance evidence requires active Admin or Reviewer observation';
    END IF;
    IF NEW.passed AND NEW.category IN ('backup_restore','worker_restart','runbook_validation') THEN
        BEGIN
            subject_uuid:=NEW.subject_id::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'Passed operations evidence requires a UUID subject';
        END;
        IF NEW.category='backup_restore' THEN
            SELECT EXISTS (
                SELECT 1 FROM football_brief.operations_restore_events
                 WHERE id=subject_uuid AND database_restored AND artifacts_restored
                   AND migration_head_verified AND database_sha256_verified
                   AND artifact_sha256_verified
            ) INTO valid_subject;
        ELSIF NEW.category='worker_restart' THEN
            SELECT EXISTS (
                SELECT 1 FROM football_brief.operations_drill_runs
                 WHERE id=subject_uuid AND drill_kind='worker_restart' AND status='passed'
            ) INTO valid_subject;
        ELSE
            SELECT EXISTS (
                SELECT 1 FROM football_brief.operations_drill_runs
                 WHERE id=subject_uuid AND drill_kind IN ('staging_recreate','security_scan')
                   AND status='passed'
            ) INTO valid_subject;
        END IF;
        IF NOT valid_subject THEN
            RAISE EXCEPTION 'Operations acceptance evidence does not match a passed canonical record';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_evidence_subject_valid
BEFORE INSERT ON football_brief.acceptance_pilot_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_evidence_insert();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_signoff()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actual_role boolean;
    item_count integer;
    passed_count integer;
    blocking_defects integer;
    missing_operations integer;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Acceptance sign-offs are append-only'; END IF;
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.operator_id AND ou.active AND our.role=NEW.signoff_role
    ) INTO actual_role;
    IF NOT actual_role THEN RAISE EXCEPTION 'Sign-off operator must hold the recorded role'; END IF;
    SELECT count(*),count(*) FILTER (WHERE status='passed') INTO item_count,passed_count
      FROM football_brief.acceptance_pilot_items WHERE pilot_id=NEW.pilot_id;
    SELECT count(*) INTO blocking_defects FROM football_brief.acceptance_pilot_defects
     WHERE pilot_id=NEW.pilot_id AND severity IN ('major','critical') AND status='open';
    WITH required(category) AS (
        VALUES ('backup_restore'),('worker_restart'),('runbook_validation')
    )
    SELECT count(*) INTO missing_operations
      FROM required r
     WHERE NOT EXISTS (
         SELECT 1 FROM football_brief.acceptance_pilot_evidence ape
         JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
          WHERE api.pilot_id=NEW.pilot_id AND ape.category=r.category AND ape.passed
     );
    IF item_count<>4 OR passed_count<>4 OR blocking_defects<>0 OR missing_operations<>0 THEN
        RAISE EXCEPTION 'Sign-off requires four passed items, operations evidence, and no blocking defect';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION football_brief.enforce_acceptance_per_brand_modes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    invalid_brand_modes integer;
BEGIN
    IF NEW.status='accepted' AND OLD.status IS DISTINCT FROM 'accepted' THEN
        SELECT count(*) INTO invalid_brand_modes
          FROM (
              SELECT brand_id,
                     count(*) FILTER (WHERE production_mode='local_only') AS local_count,
                     count(*) FILTER (WHERE production_mode='managed_render') AS managed_count
                FROM football_brief.acceptance_pilot_items
               WHERE pilot_id=NEW.id GROUP BY brand_id
          ) coverage
         WHERE coverage.local_count<>1 OR coverage.managed_count<>1;
        IF invalid_brand_modes<>0 THEN
            RAISE EXCEPTION 'Each pilot brand requires exactly one local-only and one managed-render item';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_per_brand_modes
BEFORE UPDATE ON football_brief.acceptance_pilots
FOR EACH ROW EXECUTE FUNCTION football_brief.enforce_acceptance_per_brand_modes();

COMMIT;
