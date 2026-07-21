-- Controlled delivery experiments may reuse one approved release with different delivery copy or timing.

BEGIN;

ALTER TABLE football_brief.performance_experiment_variants
    DROP CONSTRAINT performance_experiment_variants_experiment_id_final_release_id_key;

COMMENT ON COLUMN football_brief.performance_experiment_variants.final_release_id IS
    'Exact approved release used by the variant; multiple delivery variants may intentionally reuse it.';

COMMIT;
