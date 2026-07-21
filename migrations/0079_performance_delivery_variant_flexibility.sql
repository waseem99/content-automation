-- Controlled delivery experiments may reuse one approved release with different delivery copy or timing.

BEGIN;

DO $$
DECLARE
    table_oid oid:='football_brief.performance_experiment_variants'::regclass;
    experiment_attnum smallint;
    release_attnum smallint;
    constraint_name text;
BEGIN
    SELECT attnum INTO experiment_attnum
      FROM pg_attribute
     WHERE attrelid=table_oid AND attname='experiment_id' AND NOT attisdropped;
    SELECT attnum INTO release_attnum
      FROM pg_attribute
     WHERE attrelid=table_oid AND attname='final_release_id' AND NOT attisdropped;

    SELECT conname INTO constraint_name
      FROM pg_constraint
     WHERE conrelid=table_oid
       AND contype='u'
       AND conkey=ARRAY[experiment_attnum,release_attnum]::smallint[];

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
