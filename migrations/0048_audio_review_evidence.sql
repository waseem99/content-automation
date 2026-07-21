-- Exact-mix audio review actions, independent decisions, and append-only lifecycle evidence.

BEGIN;

ALTER TABLE football_brief.audio_segment_takes
    ADD CONSTRAINT audio_segment_take_production_unique
    UNIQUE (id, audio_production_id);

CREATE TABLE football_brief.audio_review_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    audio_mix_version_id uuid NOT NULL,
    paragraph_id uuid,
    segment_take_id uuid,
    action_type text NOT NULL CHECK (action_type IN (
        'pronunciation', 'pace', 'tone', 'paragraph_replacement', 'mix', 'general'
    )),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    suggested_value text,
    author_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_by_operator_id text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (audio_mix_version_id, audio_production_id)
        REFERENCES football_brief.audio_mix_versions(id, audio_production_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (paragraph_id, audio_production_id)
        REFERENCES football_brief.audio_paragraphs(id, audio_production_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (segment_take_id, audio_production_id)
        REFERENCES football_brief.audio_segment_takes(id, audio_production_id)
        ON DELETE RESTRICT,
    CONSTRAINT audio_review_action_resolution_consistent CHECK (
        (resolved_at IS NULL AND resolved_by_operator_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_operator_id IS NOT NULL)
    ),
    CONSTRAINT audio_review_action_target_present CHECK (
        action_type IN ('mix', 'general') OR paragraph_id IS NOT NULL OR segment_take_id IS NOT NULL
    )
);

CREATE INDEX audio_review_actions_mix_idx
ON football_brief.audio_review_actions (audio_mix_version_id, resolved_at, created_at);

CREATE TABLE football_brief.audio_review_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    audio_mix_version_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved', 'changes_requested', 'rejected')),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    production_lock_version bigint NOT NULL CHECK (production_lock_version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (audio_mix_version_id),
    FOREIGN KEY (audio_mix_version_id, audio_production_id)
        REFERENCES football_brief.audio_mix_versions(id, audio_production_id)
        ON DELETE RESTRICT
);

CREATE TABLE football_brief.audio_production_events (
    id bigserial PRIMARY KEY,
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    audio_mix_version_id uuid,
    paragraph_id uuid,
    segment_take_id uuid,
    event text NOT NULL CHECK (event IN (
        'initialized', 'paragraph_take_enqueued', 'paragraph_take_registered',
        'paragraph_take_selected', 'paragraph_regenerated', 'mix_built', 'mix_rebuilt',
        'submitted', 'review_action_created', 'review_action_resolved',
        'approved', 'changes_requested', 'rejected', 'superseded'
    )),
    actor text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (audio_mix_version_id, audio_production_id)
        REFERENCES football_brief.audio_mix_versions(id, audio_production_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (paragraph_id, audio_production_id)
        REFERENCES football_brief.audio_paragraphs(id, audio_production_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (segment_take_id, audio_production_id)
        REFERENCES football_brief.audio_segment_takes(id, audio_production_id)
        ON DELETE RESTRICT
);

CREATE INDEX audio_production_events_idx
ON football_brief.audio_production_events (audio_production_id, created_at, id);

CREATE OR REPLACE FUNCTION football_brief.validate_audio_review_action()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    mix_status text;
    take_paragraph_id uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audio review actions cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        SELECT amv.status INTO mix_status
          FROM football_brief.audio_mix_versions amv
         WHERE amv.id = NEW.audio_mix_version_id
           AND amv.audio_production_id = NEW.audio_production_id;
        IF mix_status NOT IN ('in_review', 'changes_requested') THEN
            RAISE EXCEPTION 'Audio review actions require a submitted mix version';
        END IF;

        IF NEW.segment_take_id IS NOT NULL AND NEW.paragraph_id IS NOT NULL THEN
            SELECT ast.paragraph_id INTO take_paragraph_id
              FROM football_brief.audio_segment_takes ast
             WHERE ast.id = NEW.segment_take_id
               AND ast.audio_production_id = NEW.audio_production_id;
            IF take_paragraph_id IS DISTINCT FROM NEW.paragraph_id THEN
                RAISE EXCEPTION 'Audio review action take belongs to another paragraph';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.resolved_at IS NOT NULL
       OR NEW.audio_production_id IS DISTINCT FROM OLD.audio_production_id
       OR NEW.audio_mix_version_id IS DISTINCT FROM OLD.audio_mix_version_id
       OR NEW.paragraph_id IS DISTINCT FROM OLD.paragraph_id
       OR NEW.segment_take_id IS DISTINCT FROM OLD.segment_take_id
       OR NEW.action_type IS DISTINCT FROM OLD.action_type
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.suggested_value IS DISTINCT FROM OLD.suggested_value
       OR NEW.author_operator_id IS DISTINCT FROM OLD.author_operator_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.resolved_at IS NULL
       OR NEW.resolved_by_operator_id IS NULL THEN
        RAISE EXCEPTION 'Audio review actions are immutable except one-time resolution';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_review_action_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_review_actions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_review_action();

CREATE OR REPLACE FUNCTION football_brief.validate_audio_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_mix_id uuid;
    current_lock bigint;
    production_status text;
    mix_status text;
    mix_last_editor text;
BEGIN
    SELECT ap.current_mix_version_id, ap.lock_version, ap.status,
           amv.status, amv.last_edited_by
      INTO current_mix_id, current_lock, production_status, mix_status, mix_last_editor
      FROM football_brief.audio_productions ap
      JOIN football_brief.audio_mix_versions amv
        ON amv.id = NEW.audio_mix_version_id
       AND amv.audio_production_id = ap.id
     WHERE ap.id = NEW.audio_production_id
     FOR UPDATE OF ap, amv;

    IF current_mix_id IS DISTINCT FROM NEW.audio_mix_version_id THEN
        RAISE EXCEPTION 'Stale audio mix versions cannot be reviewed';
    END IF;
    IF production_status IS DISTINCT FROM 'in_review' OR mix_status IS DISTINCT FROM 'in_review' THEN
        RAISE EXCEPTION 'Only submitted audio mix versions can be reviewed';
    END IF;
    IF current_lock IS DISTINCT FROM NEW.production_lock_version THEN
        RAISE EXCEPTION 'Audio review lock version is stale';
    END IF;
    IF mix_last_editor = NEW.reviewer_operator_id THEN
        RAISE EXCEPTION 'Independent audio review is required';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_review_decision_valid
BEFORE INSERT ON football_brief.audio_review_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_review_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_audio_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Audio review decisions are immutable';
END;
$$;

CREATE TRIGGER audio_review_decision_immutable
BEFORE UPDATE OR DELETE ON football_brief.audio_review_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_audio_review_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_audio_production_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Audio production events are immutable';
END;
$$;

CREATE TRIGGER audio_production_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.audio_production_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_audio_production_event();

COMMENT ON TABLE football_brief.audio_review_actions IS
    'Exact mix-version review evidence for pronunciation, pace, tone, paragraph replacement, and mix corrections.';
COMMENT ON TABLE football_brief.audio_review_decisions IS
    'Independent, lock-bound decisions for one exact submitted audio mix version.';

COMMIT;