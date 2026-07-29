-- P113 groups representative clip cases into complete pilot videos so acceptance
-- cannot confuse accepted clips with completed two-minute deliverables.

BEGIN;

CREATE TABLE football_brief.video_pilot_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pilot_run_id uuid NOT NULL REFERENCES football_brief.video_pilot_runs(id) ON DELETE RESTRICT,
    item_key text NOT NULL CHECK (item_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 300),
    portfolio_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    target_duration_seconds numeric(10,3) NOT NULL DEFAULT 120 CHECK (target_duration_seconds BETWEEN 10 AND 150),
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','production','completed','cancelled')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pilot_run_id, item_key)
);

CREATE INDEX video_pilot_items_run_idx
ON football_brief.video_pilot_items (pilot_run_id, status, item_key);

ALTER TABLE football_brief.video_pilot_cases
    ADD COLUMN pilot_item_id uuid;

-- Defensive backfill in case the calibration API was used between migrations.
INSERT INTO football_brief.video_pilot_items
    (pilot_run_id,item_key,title,target_duration_seconds,status,created_by)
SELECT r.id,'legacy-item','Legacy pilot item',120,'production',r.created_by
FROM football_brief.video_pilot_runs r
WHERE EXISTS (
    SELECT 1 FROM football_brief.video_pilot_cases c WHERE c.pilot_run_id=r.id
)
ON CONFLICT (pilot_run_id,item_key) DO NOTHING;

UPDATE football_brief.video_pilot_cases c
SET pilot_item_id=i.id
FROM football_brief.video_pilot_items i
WHERE c.pilot_run_id=i.pilot_run_id
  AND i.item_key='legacy-item'
  AND c.pilot_item_id IS NULL;

ALTER TABLE football_brief.video_pilot_cases
    ALTER COLUMN pilot_item_id SET NOT NULL,
    ADD CONSTRAINT video_pilot_case_item_fk
        FOREIGN KEY (pilot_item_id) REFERENCES football_brief.video_pilot_items(id) ON DELETE RESTRICT;

CREATE INDEX video_pilot_cases_item_idx
ON football_brief.video_pilot_cases (pilot_item_id, status, case_key);

CREATE OR REPLACE FUNCTION football_brief.validate_video_pilot_case_status()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    accepted_total integer;
BEGIN
    IF OLD.status IN ('completed','cancelled') AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Terminal pilot cases are immutable';
    END IF;
    IF OLD.status IS DISTINCT FROM 'completed' AND NEW.status = 'completed' THEN
        SELECT count(*) INTO accepted_total
          FROM football_brief.video_pilot_attempt_reviews rv
          JOIN football_brief.video_pilot_attempts a ON a.id=rv.pilot_attempt_id
         WHERE a.pilot_case_id=NEW.id
           AND a.status='succeeded'
           AND rv.decision='accepted';
        IF accepted_total <> 1 THEN
            RAISE EXCEPTION 'Completed pilot case requires exactly one accepted succeeded attempt';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER video_pilot_case_status_valid
BEFORE UPDATE ON football_brief.video_pilot_cases
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_video_pilot_case_status();

CREATE OR REPLACE FUNCTION football_brief.validate_video_pilot_item_status()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    completed_total integer;
    pending_total integer;
BEGIN
    IF OLD.status IN ('completed','cancelled') AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Terminal pilot video items are immutable';
    END IF;
    IF OLD.status IS DISTINCT FROM 'completed' AND NEW.status = 'completed' THEN
        SELECT count(*) FILTER (WHERE status='completed'),
               count(*) FILTER (WHERE status NOT IN ('completed','cancelled'))
          INTO completed_total,pending_total
          FROM football_brief.video_pilot_cases
         WHERE pilot_item_id=NEW.id;
        IF completed_total = 0 OR pending_total <> 0 THEN
            RAISE EXCEPTION 'Completed pilot video requires accepted completion of every non-cancelled case';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER video_pilot_item_status_valid
BEFORE UPDATE ON football_brief.video_pilot_items
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_video_pilot_item_status();

CREATE OR REPLACE FUNCTION football_brief.validate_video_pilot_run_status()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    completed_item_total integer;
    terminal_attempt_total integer;
BEGIN
    IF OLD.status IN ('closed','cancelled') AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Terminal video pilot runs are immutable';
    END IF;
    IF OLD.status IS DISTINCT FROM 'closed' AND NEW.status = 'closed' THEN
        SELECT count(*) INTO completed_item_total
          FROM football_brief.video_pilot_items
         WHERE pilot_run_id=NEW.id AND status='completed';
        SELECT count(*) INTO terminal_attempt_total
          FROM football_brief.video_pilot_attempts a
          JOIN football_brief.video_pilot_cases c ON c.id=a.pilot_case_id
         WHERE c.pilot_run_id=NEW.id AND a.status IN ('succeeded','failed','cancelled');
        IF completed_item_total < NEW.target_videos THEN
            RAISE EXCEPTION 'Pilot run cannot close before the completed-video target is met';
        END IF;
        IF terminal_attempt_total < NEW.target_attempts THEN
            RAISE EXCEPTION 'Pilot run cannot close before the attempt target is met';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER video_pilot_run_status_valid
BEFORE UPDATE ON football_brief.video_pilot_runs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_video_pilot_run_status();

COMMENT ON TABLE football_brief.video_pilot_items IS
    'Complete pilot-video grouping for clip-level generation cases and measured acceptance.';

COMMIT;
