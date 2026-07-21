-- Controlled delivery experiments may reuse one approved release with different delivery copy or timing.

BEGIN;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
      FROM pg_constraint
     WHERE conrelid='football_brief.performance_experiment_variants'::regclass
       AND contype='u'
       AND conname LIKE 'performance_experiment_variants_experiment_id_final_release%';
    IF constraint_name IS NULL THEN
        RAISE EXCEPTION 'Expected experiment release uniqueness constraint was not found';
    END IF;
    EXECUTE format(
        'ALTER TABLE football_brief.performance_experiment_variants DROP CONSTRAINT %I',
        constraint_name
    );
END;
$$;

COMMENT ON COLUMN football_brief.performance_experiment_variants.final_release_id IS
    'Exact approved release used by the variant; multiple delivery variants may intentionally reuse it.';

COMMIT;
