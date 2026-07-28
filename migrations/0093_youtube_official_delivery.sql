-- Activate one official live delivery path without weakening the simulated P97 boundary.
-- Only the reviewed YouTube adapter may execute non-simulated targets.

BEGIN;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT con.conname
      INTO constraint_name
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid=con.conrelid
      JOIN pg_namespace nsp ON nsp.oid=rel.relnamespace
     WHERE nsp.nspname='football_brief'
       AND rel.relname='platform_delivery_targets'
       AND con.contype='c'
       AND pg_get_constraintdef(con.oid) ILIKE '%execution_enabled%'
       AND pg_get_constraintdef(con.oid) ILIKE '%simulated%'
       AND pg_get_constraintdef(con.oid) NOT ILIKE '%youtube-official%'
     LIMIT 1;

    IF constraint_name IS NULL THEN
        RAISE EXCEPTION 'legacy simulated-only delivery target check was not found';
    END IF;

    EXECUTE format(
        'ALTER TABLE football_brief.platform_delivery_targets DROP CONSTRAINT %I',
        constraint_name
    );
END $$;

ALTER TABLE football_brief.platform_delivery_targets
    ADD CONSTRAINT platform_delivery_targets_execution_boundary_check
    CHECK (
        NOT execution_enabled
        OR simulated
        OR (
            primary_adapter_key='youtube-official'
            AND platform='youtube'
            AND credential_secret_ref IS NOT NULL
            AND environment IN ('staging','production')
        )
    );

COMMENT ON TABLE football_brief.platform_delivery_targets IS
    'Versioned platform delivery configuration. Non-simulated execution is limited to the official account-gated YouTube adapter.';

COMMIT;
