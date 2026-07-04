-- Football Brief Phase 0: validate current manifest state for deferred events
-- Depends on migrations/0006_immutable_render_manifests.sql

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_manifest_final_state()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    current_status text;
    current_mode text;
    current_nfp boolean;
BEGIN
    SELECT status, mode, not_for_publication
      INTO current_status, current_mode, current_nfp
    FROM football_brief.render_manifests
    WHERE id = NEW.id;

    IF current_status = 'draft' THEN
        RAISE EXCEPTION 'Render manifest must be sealed before commit';
    END IF;
    IF current_mode = 'preview' THEN
        IF current_status <> 'sealed' OR NOT current_nfp THEN
            RAISE EXCEPTION 'Preview manifest must be sealed and non-publishable';
        END IF;
        RETURN NEW;
    END IF;
    PERFORM football_brief.validate_publish_manifest(NEW.id);
    RETURN NEW;
END;
$$;

COMMIT;
