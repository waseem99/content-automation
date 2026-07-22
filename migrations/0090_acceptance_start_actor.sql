-- Persist and protect the actor that starts an acceptance pilot.
-- Existing started pilots are backfilled from their canonical pilot_started event.

BEGIN;

ALTER TABLE football_brief.acceptance_pilots
    ADD COLUMN IF NOT EXISTS started_by text
    REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT;

UPDATE football_brief.acceptance_pilots ap
   SET started_by = COALESCE(
       (
           SELECT ape.actor
             FROM football_brief.acceptance_pilot_events ape
            WHERE ape.pilot_id=ap.id AND ape.event_type='pilot_started'
            ORDER BY ape.created_at,ape.id
            LIMIT 1
       ),
       ap.created_by
   )
 WHERE ap.started_at IS NOT NULL
   AND ap.started_by IS NULL;

ALTER TABLE football_brief.acceptance_pilots
    DROP CONSTRAINT IF EXISTS acceptance_pilot_start_actor_required;

ALTER TABLE football_brief.acceptance_pilots
    ADD CONSTRAINT acceptance_pilot_start_actor_required
    CHECK (started_at IS NULL OR started_by IS NOT NULL) NOT VALID;

ALTER TABLE football_brief.acceptance_pilots
    VALIDATE CONSTRAINT acceptance_pilot_start_actor_required;

CREATE OR REPLACE FUNCTION football_brief.protect_acceptance_start_actor()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.status<>'draft' OR NEW.started_at IS NOT NULL OR NEW.started_by IS NOT NULL THEN
            RAISE EXCEPTION 'New acceptance pilots must begin as unstarted drafts';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.started_by IS DISTINCT FROM OLD.started_by THEN
        IF NOT (
            OLD.status='draft'
            AND NEW.status='running'
            AND OLD.started_by IS NULL
            AND NEW.started_by IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Acceptance pilot start actor is immutable';
        END IF;
    END IF;

    IF OLD.status='draft' AND NEW.status='running' THEN
        IF NEW.started_at IS NULL OR NEW.started_by IS NULL THEN
            RAISE EXCEPTION 'Acceptance pilot start requires actor and timestamp';
        END IF;
    ELSIF NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'Acceptance pilot start timestamp is immutable';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS acceptance_pilot_start_actor_valid
ON football_brief.acceptance_pilots;

CREATE TRIGGER acceptance_pilot_start_actor_valid
BEFORE INSERT OR UPDATE ON football_brief.acceptance_pilots
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_start_actor();

COMMIT;
