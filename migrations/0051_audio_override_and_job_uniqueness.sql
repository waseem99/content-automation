-- Preserve multiple pronunciation revisions while allowing one active value, and bind one job to one take.

BEGIN;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
      FROM pg_constraint
     WHERE conrelid = 'football_brief.audio_pronunciation_overrides'::regclass
       AND contype = 'u'
       AND pg_get_constraintdef(oid) ILIKE '%audio_production_id%token%locale%active%'
     LIMIT 1;
    IF constraint_name IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE football_brief.audio_pronunciation_overrides DROP CONSTRAINT %I',
            constraint_name
        );
    END IF;
END;
$$;

CREATE UNIQUE INDEX audio_pronunciation_one_active_idx
ON football_brief.audio_pronunciation_overrides (audio_production_id, lower(token), lower(locale))
WHERE active = true;

CREATE UNIQUE INDEX audio_segment_take_generation_job_idx
ON football_brief.audio_segment_takes (generation_job_id)
WHERE generation_job_id IS NOT NULL;

COMMIT;