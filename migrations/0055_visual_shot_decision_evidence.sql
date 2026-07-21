-- Exact shot-version change and rejection evidence used before prompt revisions.

BEGIN;

CREATE TABLE football_brief.visual_shot_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    visual_shot_id uuid NOT NULL,
    visual_shot_version_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('changes_requested','rejected')),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    shot_lock_version bigint NOT NULL CHECK (shot_lock_version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (visual_shot_version_id),
    FOREIGN KEY (visual_shot_id, visual_project_id)
        REFERENCES football_brief.visual_shots(id, visual_project_id) ON DELETE RESTRICT,
    FOREIGN KEY (visual_shot_version_id, visual_shot_id)
        REFERENCES football_brief.visual_shot_versions(id, visual_shot_id) ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION football_brief.validate_visual_shot_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_version uuid;
    current_lock bigint;
    shot_status text;
    version_status text;
    last_editor text;
BEGIN
    SELECT vs.current_version_id,vs.lock_version,vs.status,vsv.status,vsv.last_edited_by
      INTO current_version,current_lock,shot_status,version_status,last_editor
      FROM football_brief.visual_shots vs
      JOIN football_brief.visual_shot_versions vsv
        ON vsv.id=NEW.visual_shot_version_id AND vsv.visual_shot_id=vs.id
     WHERE vs.id=NEW.visual_shot_id AND vs.visual_project_id=NEW.visual_project_id
     FOR UPDATE OF vs,vsv;
    IF current_version IS DISTINCT FROM NEW.visual_shot_version_id THEN
        RAISE EXCEPTION 'Stale visual shot versions cannot receive revision decisions';
    END IF;
    IF current_lock IS DISTINCT FROM NEW.shot_lock_version THEN
        RAISE EXCEPTION 'Visual shot revision decision lock is stale';
    END IF;
    IF shot_status<>'candidates_ready' OR version_status<>'candidates_ready' THEN
        RAISE EXCEPTION 'Visual shot revision decisions require a candidate-ready version';
    END IF;
    IF last_editor=NEW.reviewer_operator_id THEN
        RAISE EXCEPTION 'Independent visual shot review is required';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_shot_decision_valid
BEFORE INSERT ON football_brief.visual_shot_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_shot_decision();

CREATE OR REPLACE FUNCTION football_brief.apply_visual_shot_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE football_brief.visual_shot_versions
       SET status=NEW.decision,decided_at=now()
     WHERE id=NEW.visual_shot_version_id AND status='candidates_ready';
    IF NOT FOUND THEN RAISE EXCEPTION 'Visual shot version could not accept the review decision'; END IF;

    UPDATE football_brief.visual_shots
       SET status=NEW.decision,lock_version=lock_version+1
     WHERE id=NEW.visual_shot_id AND lock_version=NEW.shot_lock_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'Visual shot could not accept the review decision'; END IF;

    INSERT INTO football_brief.visual_project_events
        (visual_project_id,visual_shot_id,visual_shot_version_id,event,actor,details)
    VALUES (
        NEW.visual_project_id,NEW.visual_shot_id,NEW.visual_shot_version_id,
        CASE NEW.decision WHEN 'changes_requested' THEN 'review_action_created' ELSE 'candidate_rejected' END,
        NEW.reviewer_operator_id,
        jsonb_build_object('shot_decision_id',NEW.id,'decision',NEW.decision,'rationale',NEW.rationale)
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_shot_decision_apply
AFTER INSERT ON football_brief.visual_shot_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_visual_shot_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_shot_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Visual shot decisions are immutable'; END;
$$;

CREATE TRIGGER visual_shot_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.visual_shot_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_shot_decision();

COMMIT;