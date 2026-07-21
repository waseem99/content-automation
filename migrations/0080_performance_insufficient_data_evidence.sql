-- An experiment with no imported observations must still retain an explicit insufficient-data evaluation.

BEGIN;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
      FROM pg_constraint
     WHERE conrelid='football_brief.performance_experiment_results'::regclass
       AND contype='c'
       AND pg_get_constraintdef(oid) ILIKE '%cardinality(evaluated_observation_ids)%';
    IF constraint_name IS NULL THEN
        RAISE EXCEPTION 'Expected experiment observation evidence check was not found';
    END IF;
    EXECUTE format(
        'ALTER TABLE football_brief.performance_experiment_results DROP CONSTRAINT %I',
        constraint_name
    );
END;
$$;

ALTER TABLE football_brief.performance_experiment_results
    ADD CONSTRAINT performance_experiment_result_evidence_required CHECK (
        (result_status='insufficient_data' AND cardinality(evaluated_observation_ids)>=0)
        OR (result_status IN ('meaningful_result','no_winner')
            AND cardinality(evaluated_observation_ids)>=1)
    );

COMMIT;
