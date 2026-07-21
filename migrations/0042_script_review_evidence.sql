-- Version-bound script review actions and exact-version decisions.

BEGIN;

CREATE TABLE football_brief.script_review_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    script_section_id uuid,
    claim_id uuid,
    action_type text NOT NULL CHECK (action_type IN (
        'inline_edit', 'factual_query', 'source_request', 'tone_change', 'general'
    )),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    suggested_text text,
    author_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_by_operator_id text
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT script_review_action_resolution_consistent CHECK (
        (resolved_at IS NULL AND resolved_by_operator_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_operator_id IS NOT NULL)
    ),
    CONSTRAINT script_review_action_target_present CHECK (
        script_section_id IS NOT NULL OR claim_id IS NOT NULL OR action_type = 'general'
    )
);

CREATE INDEX script_review_actions_version_idx
ON football_brief.script_review_actions (script_version_id, resolved_at, created_at);

CREATE TABLE football_brief.script_review_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_document_id uuid NOT NULL
        REFERENCES football_brief.script_documents(id) ON DELETE RESTRICT,
    script_version_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved', 'changes_requested', 'rejected')),
    reviewer_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    document_lock_version bigint NOT NULL CHECK (document_lock_version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (script_version_id),
    FOREIGN KEY (script_version_id, script_document_id)
        REFERENCES football_brief.script_versions(id, script_document_id)
        ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION football_brief.validate_script_review_action()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_version_id uuid;
    target_status text;
    section_version_id uuid;
    claim_version_id uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Script review actions cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        target_version_id := NEW.script_version_id;
    ELSE
        target_version_id := OLD.script_version_id;
    END IF;

    SELECT sv.status INTO target_status
      FROM football_brief.script_versions sv
     WHERE sv.id = target_version_id;

    IF TG_OP = 'INSERT' THEN
        IF target_status NOT IN ('in_review', 'changes_requested') THEN
            RAISE EXCEPTION 'Review actions require a submitted script version';
        END IF;
        IF NEW.script_section_id IS NOT NULL THEN
            SELECT ss.script_version_id INTO section_version_id
              FROM football_brief.script_sections ss
             WHERE ss.id = NEW.script_section_id;
            IF section_version_id IS DISTINCT FROM NEW.script_version_id THEN
                RAISE EXCEPTION 'Script review action section belongs to another version';
            END IF;
        END IF;
        IF NEW.claim_id IS NOT NULL THEN
            SELECT sc.script_version_id INTO claim_version_id
              FROM football_brief.script_claims sc
             WHERE sc.id = NEW.claim_id;
            IF claim_version_id IS DISTINCT FROM NEW.script_version_id THEN
                RAISE EXCEPTION 'Script review action claim belongs to another version';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.resolved_at IS NOT NULL
       OR NEW.script_version_id IS DISTINCT FROM OLD.script_version_id
       OR NEW.script_section_id IS DISTINCT FROM OLD.script_section_id
       OR NEW.claim_id IS DISTINCT FROM OLD.claim_id
       OR NEW.action_type IS DISTINCT FROM OLD.action_type
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.suggested_text IS DISTINCT FROM OLD.suggested_text
       OR NEW.author_operator_id IS DISTINCT FROM OLD.author_operator_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.resolved_at IS NULL
       OR NEW.resolved_by_operator_id IS NULL THEN
        RAISE EXCEPTION 'Script review actions are immutable except one-time resolution';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER script_review_action_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_review_actions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_script_review_action();

CREATE OR REPLACE FUNCTION football_brief.validate_script_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_version_id uuid;
    current_lock_version bigint;
    version_status text;
    version_last_editor text;
BEGIN
    SELECT sd.current_version_id, sd.lock_version, sv.status, sv.last_edited_by
      INTO current_version_id, current_lock_version, version_status, version_last_editor
      FROM football_brief.script_documents sd
      JOIN football_brief.script_versions sv
        ON sv.id = NEW.script_version_id
       AND sv.script_document_id = sd.id
     WHERE sd.id = NEW.script_document_id
     FOR UPDATE OF sd, sv;

    IF current_version_id IS DISTINCT FROM NEW.script_version_id THEN
        RAISE EXCEPTION 'Stale script versions cannot be reviewed';
    END IF;
    IF version_status IS DISTINCT FROM 'in_review' THEN
        RAISE EXCEPTION 'Only submitted script versions can be reviewed';
    END IF;
    IF current_lock_version IS DISTINCT FROM NEW.document_lock_version THEN
        RAISE EXCEPTION 'Script review lock version is stale';
    END IF;
    IF version_last_editor = NEW.reviewer_operator_id THEN
        RAISE EXCEPTION 'Independent script review is required';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER script_review_decision_valid
BEFORE INSERT ON football_brief.script_review_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_script_review_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_script_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Script review decisions are immutable';
END;
$$;

CREATE TRIGGER script_review_decision_immutable
BEFORE UPDATE OR DELETE ON football_brief.script_review_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_decision();

COMMENT ON TABLE football_brief.script_review_actions IS
    'Version-bound inline edit, factual, source, tone, and general review evidence retained across revisions.';

COMMIT;
