-- Require available shared media at every release boundary and permit QA correction/recheck.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.require_available_release_input_object()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    available_count integer;
BEGIN
    SELECT count(*) INTO available_count
      FROM football_brief.shared_artifact_object_roles saor
      JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
     WHERE saor.artifact_version_id=NEW.artifact_version_id
       AND saor.role='original'
       AND sso.asset_id=NEW.canonical_asset_id
       AND sso.status='available';
    IF available_count<>1 THEN
        RAISE EXCEPTION 'Final release input requires the exact available shared original object';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_input_object_available
BEFORE INSERT ON football_brief.final_release_inputs
FOR EACH ROW EXECUTE FUNCTION football_brief.require_available_release_input_object();

CREATE OR REPLACE FUNCTION football_brief.require_available_release_qa_output()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    available_count integer;
BEGIN
    SELECT count(*) INTO available_count
      FROM football_brief.shared_artifact_object_roles saor
      JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
     WHERE saor.artifact_version_id=NEW.output_artifact_version_id
       AND saor.role='original'
       AND sso.status='available';
    IF available_count<>1 THEN
        RAISE EXCEPTION 'Technical QA requires the exact available shared output object';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_qa_output_available
BEFORE INSERT ON football_brief.final_release_qa_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.require_available_release_qa_output();

CREATE OR REPLACE FUNCTION football_brief.require_passing_qa_for_release_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    latest_qa football_brief.final_release_qa_reports%ROWTYPE;
BEGIN
    IF OLD.status='assembled' AND NEW.status='qa_complete' THEN
        SELECT * INTO latest_qa
          FROM football_brief.final_release_qa_reports
         WHERE release_id=OLD.id
         ORDER BY created_at DESC,id DESC
         LIMIT 1;
        IF latest_qa.id IS NULL OR latest_qa.outcome<>'pass'
           OR latest_qa.output_artifact_version_id IS DISTINCT FROM OLD.output_artifact_version_id THEN
            RAISE EXCEPTION 'Only passing technical QA can advance a final release';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_passing_qa_transition
BEFORE UPDATE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.require_passing_qa_for_release_transition();

CREATE OR REPLACE FUNCTION football_brief.require_current_available_release_approval()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    invalid_inputs integer;
    output_available integer;
BEGIN
    IF OLD.status='in_review' AND NEW.status='approved' THEN
        SELECT count(*) INTO invalid_inputs
          FROM football_brief.final_release_inputs fri
          JOIN football_brief.shared_artifact_versions sav ON sav.id=fri.artifact_version_id
          JOIN football_brief.assets a ON a.id=fri.canonical_asset_id
          LEFT JOIN LATERAL (
              SELECT decision
                FROM football_brief.final_release_input_approvals fra
               WHERE fra.artifact_version_id=fri.artifact_version_id
                 AND fra.role=fri.role
               ORDER BY created_at DESC,id DESC
               LIMIT 1
          ) latest ON true
          LEFT JOIN LATERAL (
              SELECT count(*) AS count
                FROM football_brief.shared_artifact_object_roles saor
                JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
               WHERE saor.artifact_version_id=fri.artifact_version_id
                 AND saor.role='original'
                 AND sso.asset_id=fri.canonical_asset_id
                 AND sso.status='available'
          ) shared ON true
         WHERE fri.release_id=OLD.id
           AND fri.required
           AND (
               sav.status<>'current'
               OR a.sha256 IS DISTINCT FROM fri.asset_sha256
               OR latest.decision IS DISTINCT FROM 'approved'
               OR shared.count<>1
           );

        SELECT count(*) INTO output_available
          FROM football_brief.shared_artifact_object_roles saor
          JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
         WHERE saor.artifact_version_id=OLD.output_artifact_version_id
           AND saor.role='original'
           AND sso.status='available';

        IF invalid_inputs<>0 OR output_available<>1 THEN
            RAISE EXCEPTION 'Final approval requires current approved inputs and available shared media';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_current_available_approval
BEFORE UPDATE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.require_current_available_release_approval();

COMMIT;
