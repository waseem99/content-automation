-- Football Brief Phase 0: fail closed on invalid publication references
-- Depends on migrations/0008_publish_manifest_validation.sql

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_publication_package()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    manifest_mode text;
    manifest_status text;
    manifest_nfp boolean;
    job_mode text;
    job_nfp boolean;
BEGIN
    SELECT mode, status, not_for_publication
      INTO manifest_mode, manifest_status, manifest_nfp
    FROM football_brief.render_manifests
    WHERE id = NEW.render_manifest_id;

    SELECT mode, not_for_publication
      INTO job_mode, job_nfp
    FROM football_brief.render_jobs
    WHERE id = NEW.render_job_id
      AND render_manifest_id = NEW.render_manifest_id;

    IF manifest_mode IS DISTINCT FROM 'publish'
       OR manifest_status IS DISTINCT FROM 'approved'
       OR manifest_nfp IS DISTINCT FROM false
       OR job_mode IS DISTINCT FROM 'publish'
       OR job_nfp IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Preview or unapproved output cannot enter a publication package';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
