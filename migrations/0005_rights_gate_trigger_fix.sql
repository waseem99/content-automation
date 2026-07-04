-- Football Brief Phase 0: correct deferred evidence trigger row handling
-- Depends on migrations/0004_rights_gate_audit.sql

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.require_evidence_for_approved_rights()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    target_rights_id uuid;
    current_status text;
BEGIN
    IF TG_TABLE_NAME = 'asset_rights' THEN
        target_rights_id := NEW.id;
    ELSE
        target_rights_id := OLD.asset_rights_id;
    END IF;

    SELECT approval_status INTO current_status
    FROM football_brief.asset_rights
    WHERE id = target_rights_id;

    IF current_status = 'approved' AND NOT EXISTS (
        SELECT 1
        FROM football_brief.asset_rights_evidence_links
        WHERE asset_rights_id = target_rights_id
    ) THEN
        RAISE EXCEPTION 'Approved rights require linked evidence';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
