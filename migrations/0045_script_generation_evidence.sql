-- Retain deterministic/local adapter evidence on every script version.

BEGIN;

ALTER TABLE football_brief.script_versions
    ADD COLUMN generation_evidence jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
