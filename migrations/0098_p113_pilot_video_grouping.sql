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

COMMENT ON TABLE football_brief.video_pilot_items IS
    'Complete pilot-video grouping for clip-level generation cases and measured acceptance.';

COMMIT;
