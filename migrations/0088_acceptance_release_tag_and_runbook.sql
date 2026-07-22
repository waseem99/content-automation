-- Bind successful P100 acceptance to one immutable production release tag and the exact operator runbook.
-- This records acceptance output only; it does not create a Git tag, deploy, or publish content.

BEGIN;

ALTER TABLE football_brief.acceptance_pilots
    ADD COLUMN production_release_tag text,
    ADD COLUMN release_tagged_by text
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    ADD COLUMN release_tagged_at timestamptz,
    ADD COLUMN runbook_path text,
    ADD COLUMN runbook_sha256 char(64),
    ADD CONSTRAINT acceptance_production_release_tag_format CHECK (
        production_release_tag IS NULL
        OR production_release_tag ~ '^prod-[a-z0-9][a-z0-9._-]{3,154}$'
    ),
    ADD CONSTRAINT acceptance_runbook_path_exact CHECK (
        runbook_path IS NULL
        OR runbook_path='docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md'
    ),
    ADD CONSTRAINT acceptance_runbook_sha256_format CHECK (
        runbook_sha256 IS NULL OR runbook_sha256 ~ '^[0-9a-f]{64}$'
    ),
    ADD CONSTRAINT acceptance_release_output_complete CHECK (
        (
            status='accepted'
            AND production_release_tag IS NOT NULL
            AND release_tagged_by IS NOT NULL
            AND release_tagged_at IS NOT NULL
            AND runbook_path IS NOT NULL
            AND runbook_sha256 IS NOT NULL
        )
        OR
        (
            status<>'accepted'
            AND production_release_tag IS NULL
            AND release_tagged_by IS NULL
            AND release_tagged_at IS NULL
            AND runbook_path IS NULL
            AND runbook_sha256 IS NULL
        )
    );

CREATE UNIQUE INDEX acceptance_production_release_tag_unique_idx
ON football_brief.acceptance_pilots(production_release_tag)
WHERE production_release_tag IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_release_output()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.production_release_tag IS NOT NULL
           OR NEW.release_tagged_by IS NOT NULL
           OR NEW.release_tagged_at IS NOT NULL
           OR NEW.runbook_path IS NOT NULL
           OR NEW.runbook_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'Acceptance release output can only be assigned during successful acceptance';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status='accepted' THEN
        IF OLD.status NOT IN ('running','blocked') THEN
            RAISE EXCEPTION 'Acceptance release output requires an active pilot transition';
        END IF;
        IF NEW.production_release_tag IS NULL
           OR NEW.release_tagged_by IS NULL
           OR NEW.release_tagged_at IS NULL
           OR NEW.runbook_path IS NULL
           OR NEW.runbook_sha256 IS NULL THEN
            RAISE EXCEPTION 'Accepted pilots require a complete release tag and runbook binding';
        END IF;
        IF NEW.release_tagged_by IS DISTINCT FROM NEW.accepted_by
           OR NEW.release_tagged_at IS DISTINCT FROM NEW.accepted_at THEN
            RAISE EXCEPTION 'Acceptance actor and release-tag actor must be identical';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.production_release_tag IS NOT NULL
       OR NEW.release_tagged_by IS NOT NULL
       OR NEW.release_tagged_at IS NOT NULL
       OR NEW.runbook_path IS NOT NULL
       OR NEW.runbook_sha256 IS NOT NULL THEN
        RAISE EXCEPTION 'Release tag and runbook binding are forbidden before acceptance';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilots_release_output_valid
BEFORE INSERT OR UPDATE ON football_brief.acceptance_pilots
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_release_output();

COMMENT ON COLUMN football_brief.acceptance_pilots.production_release_tag IS
    'Immutable production release label defined only by a fully accepted P100 pilot; no Git tag or deployment is created automatically.';
COMMENT ON COLUMN football_brief.acceptance_pilots.runbook_sha256 IS
    'SHA-256 of the packaged non-developer P100 acceptance runbook verified by the application before acceptance.';

COMMIT;
