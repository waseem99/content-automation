-- Downstream narration and preview work must pin an exact approved script version.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_script_document_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Script documents cannot be deleted';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER script_document_delete_protected
BEFORE DELETE ON football_brief.script_documents
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_document_evidence();

CREATE OR REPLACE FUNCTION football_brief.require_approved_script_for_media_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    script_version_text text;
    requested_script_version_id uuid;
    approved_script_total integer;
    scene_total integer;
BEGIN
    IF NEW.job_type NOT IN ('narration', 'preview') THEN
        RETURN NEW;
    END IF;

    script_version_text := NEW.input_payload ->> 'script_version_id';
    IF script_version_text IS NULL
       OR script_version_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN
        RAISE EXCEPTION 'Narration and preview jobs require an approved script_version_id';
    END IF;

    requested_script_version_id := script_version_text::uuid;

    SELECT count(*) INTO approved_script_total
      FROM football_brief.script_versions sv
      JOIN football_brief.script_documents sd
        ON sd.id = sv.script_document_id
     WHERE sv.id = requested_script_version_id
       AND sv.status = 'approved'
       AND sd.current_version_id = sv.id
       AND sd.portfolio_content_id = NEW.portfolio_content_id
       AND sv.basis_content_version = NEW.content_version;

    SELECT count(*) INTO scene_total
      FROM football_brief.script_scene_plan_entries sp
     WHERE sp.script_version_id = requested_script_version_id;

    IF approved_script_total <> 1 OR scene_total = 0 THEN
        RAISE EXCEPTION 'Narration and preview jobs require an approved script and scene plan';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_script_gate
BEFORE INSERT ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.require_approved_script_for_media_job();

COMMIT;
