-- Fail-closed lineage, brand access, immutable comments, and auditable revision-task transitions.

BEGIN;

ALTER TABLE football_brief.creator_revision_tasks
    ADD COLUMN updated_by_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION football_brief.creator_operator_can_access_content(
    p_operator_id text,
    p_content_id uuid
) RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM football_brief.operator_users ou
        JOIN football_brief.monthly_content_plans mp
          ON mp.id=(SELECT pc.plan_id FROM football_brief.portfolio_content pc WHERE pc.id=p_content_id)
        WHERE ou.operator_id=p_operator_id
          AND ou.active=true
          AND (
              EXISTS (
                  SELECT 1 FROM football_brief.operator_user_roles our
                  WHERE our.operator_user_id=ou.id AND our.role='admin'
              )
              OR EXISTS (
                  SELECT 1 FROM football_brief.operator_brand_assignments oba
                  WHERE oba.operator_user_id=ou.id AND oba.brand_id=mp.brand_id
              )
          )
    );
$$;

CREATE OR REPLACE FUNCTION football_brief.validate_creator_review_comment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_content_id uuid;
    mix_duration_ms bigint;
    task_status text;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Creator review comments cannot be deleted';
    END IF;

    IF TG_OP='UPDATE' THEN
        IF OLD.resolved_at IS NOT NULL
           OR NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
           OR NEW.production_workflow_id IS DISTINCT FROM OLD.production_workflow_id
           OR NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id
           OR NEW.stage IS DISTINCT FROM OLD.stage
           OR NEW.target_type IS DISTINCT FROM OLD.target_type
           OR NEW.target_workflow_version_id IS DISTINCT FROM OLD.target_workflow_version_id
           OR NEW.target_script_version_id IS DISTINCT FROM OLD.target_script_version_id
           OR NEW.target_script_section_id IS DISTINCT FROM OLD.target_script_section_id
           OR NEW.target_audio_mix_version_id IS DISTINCT FROM OLD.target_audio_mix_version_id
           OR NEW.target_audio_paragraph_id IS DISTINCT FROM OLD.target_audio_paragraph_id
           OR NEW.target_visual_shot_version_id IS DISTINCT FROM OLD.target_visual_shot_version_id
           OR NEW.target_visual_candidate_id IS DISTINCT FROM OLD.target_visual_candidate_id
           OR NEW.timeline_start_ms IS DISTINCT FROM OLD.timeline_start_ms
           OR NEW.timeline_end_ms IS DISTINCT FROM OLD.timeline_end_ms
           OR NEW.comment_type IS DISTINCT FROM OLD.comment_type
           OR NEW.body IS DISTINCT FROM OLD.body
           OR NEW.blocking IS DISTINCT FROM OLD.blocking
           OR NEW.author_operator_id IS DISTINCT FROM OLD.author_operator_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.resolved_at IS NULL
           OR NEW.resolved_by_operator_id IS NULL THEN
            RAISE EXCEPTION 'Creator review comments are immutable except one-time resolution';
        END IF;
        IF OLD.blocking THEN
            SELECT crt.status INTO task_status
              FROM football_brief.creator_revision_tasks crt
             WHERE crt.source_comment_id=OLD.id;
            IF task_status IS DISTINCT FROM 'completed' THEN
                RAISE EXCEPTION 'Blocking change requests can resolve only after task completion';
            END IF;
        END IF;
        IF NOT football_brief.creator_operator_can_access_content(
            NEW.resolved_by_operator_id, NEW.portfolio_content_id
        ) THEN
            RAISE EXCEPTION 'Comment resolver lacks active brand access';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.blocking AND NEW.comment_type<>'change_request' THEN
        RAISE EXCEPTION 'Blocking comments must be structured change requests';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM football_brief.production_workflows pw
          JOIN football_brief.production_workflow_versions pwv
            ON pwv.id=NEW.workflow_version_id AND pwv.workflow_id=pw.id
         WHERE pw.id=NEW.production_workflow_id
           AND pw.portfolio_content_id=NEW.portfolio_content_id
    ) THEN
        RAISE EXCEPTION 'Creator review workflow context does not match content and version';
    END IF;

    IF NOT football_brief.creator_operator_can_access_content(
        NEW.author_operator_id, NEW.portfolio_content_id
    ) THEN
        RAISE EXCEPTION 'Comment author lacks active brand access';
    END IF;

    CASE NEW.target_type
        WHEN 'workflow_version' THEN
            SELECT pw.portfolio_content_id INTO target_content_id
              FROM football_brief.production_workflow_versions pwv
              JOIN football_brief.production_workflows pw ON pw.id=pwv.workflow_id
             WHERE pwv.id=NEW.target_workflow_version_id;
        WHEN 'script_version' THEN
            SELECT sd.portfolio_content_id INTO target_content_id
              FROM football_brief.script_versions sv
              JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
             WHERE sv.id=NEW.target_script_version_id;
        WHEN 'script_section' THEN
            SELECT sd.portfolio_content_id INTO target_content_id
              FROM football_brief.script_sections ss
              JOIN football_brief.script_versions sv ON sv.id=ss.script_version_id
              JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
             WHERE ss.id=NEW.target_script_section_id;
        WHEN 'audio_mix_version' THEN
            SELECT ap.portfolio_content_id,
                   CASE WHEN amv.duration_seconds IS NULL THEN NULL
                        ELSE round(amv.duration_seconds*1000)::bigint END
              INTO target_content_id,mix_duration_ms
              FROM football_brief.audio_mix_versions amv
              JOIN football_brief.audio_productions ap ON ap.id=amv.audio_production_id
             WHERE amv.id=NEW.target_audio_mix_version_id;
        WHEN 'audio_paragraph' THEN
            SELECT ap.portfolio_content_id INTO target_content_id
              FROM football_brief.audio_paragraphs apar
              JOIN football_brief.audio_productions ap ON ap.id=apar.audio_production_id
             WHERE apar.id=NEW.target_audio_paragraph_id;
        WHEN 'visual_shot_version' THEN
            SELECT vp.portfolio_content_id INTO target_content_id
              FROM football_brief.visual_shot_versions vsv
              JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
              JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
             WHERE vsv.id=NEW.target_visual_shot_version_id;
        WHEN 'visual_candidate' THEN
            SELECT vp.portfolio_content_id INTO target_content_id
              FROM football_brief.visual_candidates vc
              JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
              JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
              JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
             WHERE vc.id=NEW.target_visual_candidate_id;
    END CASE;

    IF target_content_id IS DISTINCT FROM NEW.portfolio_content_id THEN
        RAISE EXCEPTION 'Creator review target belongs to another content item';
    END IF;
    IF NEW.timeline_end_ms IS NOT NULL
       AND mix_duration_ms IS NOT NULL
       AND NEW.timeline_end_ms > mix_duration_ms THEN
        RAISE EXCEPTION 'Timed annotation exceeds the exact audio mix duration';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER creator_review_comment_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.creator_review_comments
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_creator_review_comment();

CREATE OR REPLACE FUNCTION football_brief.require_creator_change_request_task()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.comment_type='change_request'
       AND NOT EXISTS (
           SELECT 1 FROM football_brief.creator_revision_tasks crt
           WHERE crt.source_comment_id=NEW.id
       ) THEN
        RAISE EXCEPTION 'Every structured change request must create one revision task';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER creator_change_request_has_task
AFTER INSERT ON football_brief.creator_review_comments
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION football_brief.require_creator_change_request_task();

CREATE OR REPLACE FUNCTION football_brief.validate_creator_revision_task()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    source_row football_brief.creator_review_comments%ROWTYPE;
    changed_dimensions integer;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Creator revision tasks cannot be deleted';
    END IF;

    IF TG_OP='INSERT' THEN
        SELECT * INTO source_row
          FROM football_brief.creator_review_comments crc
         WHERE crc.id=NEW.source_comment_id
         FOR UPDATE;
        IF source_row.id IS NULL OR source_row.comment_type<>'change_request' THEN
            RAISE EXCEPTION 'Revision tasks require a structured change-request comment';
        END IF;
        IF source_row.resolved_at IS NOT NULL THEN
            RAISE EXCEPTION 'Resolved comments cannot create revision tasks';
        END IF;
        IF NEW.portfolio_content_id IS DISTINCT FROM source_row.portfolio_content_id
           OR NEW.production_workflow_id IS DISTINCT FROM source_row.production_workflow_id
           OR NEW.workflow_version_id IS DISTINCT FROM source_row.workflow_version_id
           OR NEW.stage IS DISTINCT FROM source_row.stage
           OR NEW.target_type IS DISTINCT FROM source_row.target_type
           OR NEW.target_workflow_version_id IS DISTINCT FROM source_row.target_workflow_version_id
           OR NEW.target_script_version_id IS DISTINCT FROM source_row.target_script_version_id
           OR NEW.target_script_section_id IS DISTINCT FROM source_row.target_script_section_id
           OR NEW.target_audio_mix_version_id IS DISTINCT FROM source_row.target_audio_mix_version_id
           OR NEW.target_audio_paragraph_id IS DISTINCT FROM source_row.target_audio_paragraph_id
           OR NEW.target_visual_shot_version_id IS DISTINCT FROM source_row.target_visual_shot_version_id
           OR NEW.target_visual_candidate_id IS DISTINCT FROM source_row.target_visual_candidate_id THEN
            RAISE EXCEPTION 'Revision task must retain the exact comment target and workflow context';
        END IF;
        IF NEW.lock_version<>1 OR NEW.status<>'open' THEN
            RAISE EXCEPTION 'New revision tasks must start open at lock version one';
        END IF;
    ELSE
        IF NEW.lock_version<>OLD.lock_version+1 THEN
            RAISE EXCEPTION 'Revision task updates must increment lock_version by exactly one';
        END IF;
        IF NEW.source_comment_id IS DISTINCT FROM OLD.source_comment_id
           OR NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
           OR NEW.production_workflow_id IS DISTINCT FROM OLD.production_workflow_id
           OR NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id
           OR NEW.stage IS DISTINCT FROM OLD.stage
           OR NEW.target_type IS DISTINCT FROM OLD.target_type
           OR NEW.target_workflow_version_id IS DISTINCT FROM OLD.target_workflow_version_id
           OR NEW.target_script_version_id IS DISTINCT FROM OLD.target_script_version_id
           OR NEW.target_script_section_id IS DISTINCT FROM OLD.target_script_section_id
           OR NEW.target_audio_mix_version_id IS DISTINCT FROM OLD.target_audio_mix_version_id
           OR NEW.target_audio_paragraph_id IS DISTINCT FROM OLD.target_audio_paragraph_id
           OR NEW.target_visual_shot_version_id IS DISTINCT FROM OLD.target_visual_shot_version_id
           OR NEW.target_visual_candidate_id IS DISTINCT FROM OLD.target_visual_candidate_id
           OR NEW.task_type IS DISTINCT FROM OLD.task_type
           OR NEW.title IS DISTINCT FROM OLD.title
           OR NEW.instructions IS DISTINCT FROM OLD.instructions
           OR NEW.assigned_by_operator_id IS DISTINCT FROM OLD.assigned_by_operator_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Revision task identity and instructions are immutable';
        END IF;
        changed_dimensions :=
            (NEW.status IS DISTINCT FROM OLD.status)::integer
          + (NEW.assignee_operator_id IS DISTINCT FROM OLD.assignee_operator_id)::integer
          + (NEW.due_at IS DISTINCT FROM OLD.due_at)::integer
          + (NEW.priority IS DISTINCT FROM OLD.priority)::integer
          + (NEW.blocker IS DISTINCT FROM OLD.blocker)::integer;
        IF changed_dimensions<>1 THEN
            RAISE EXCEPTION 'Each revision task update must change exactly one auditable dimension';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            IF OLD.status='open' AND NEW.status IN ('in_progress','completed','cancelled') THEN NULL;
            ELSIF OLD.status='in_progress' AND NEW.status IN ('completed','cancelled') THEN NULL;
            ELSE RAISE EXCEPTION 'Invalid revision task status transition';
            END IF;
        ELSIF OLD.status IN ('completed','cancelled') THEN
            RAISE EXCEPTION 'Terminal revision tasks cannot be changed';
        END IF;
    END IF;

    IF NOT football_brief.creator_operator_can_access_content(
        NEW.assignee_operator_id, NEW.portfolio_content_id
    ) THEN
        RAISE EXCEPTION 'Revision task assignee lacks active brand access';
    END IF;
    IF NOT football_brief.creator_operator_can_access_content(
        NEW.updated_by_operator_id, NEW.portfolio_content_id
    ) THEN
        RAISE EXCEPTION 'Revision task actor lacks active brand access';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER creator_revision_task_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.creator_revision_tasks
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_creator_revision_task();

CREATE OR REPLACE FUNCTION football_brief.record_creator_revision_task_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_name text;
    details_payload jsonb;
BEGIN
    IF TG_OP='INSERT' THEN
        INSERT INTO football_brief.creator_revision_task_events
            (task_id,event,actor_operator_id,from_lock_version,to_lock_version,details)
        VALUES (
            NEW.id,'created',NEW.updated_by_operator_id,NULL,1,
            jsonb_build_object(
                'assignee_operator_id',NEW.assignee_operator_id,
                'due_at',NEW.due_at,
                'priority',NEW.priority,
                'blocker',NEW.blocker
            )
        );
        RETURN NEW;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        event_name := CASE NEW.status
            WHEN 'in_progress' THEN 'started'
            WHEN 'completed' THEN 'completed'
            WHEN 'cancelled' THEN 'cancelled'
        END;
        details_payload := jsonb_build_object('from_status',OLD.status,'to_status',NEW.status);
    ELSIF NEW.assignee_operator_id IS DISTINCT FROM OLD.assignee_operator_id THEN
        event_name := 'reassigned';
        details_payload := jsonb_build_object(
            'from_assignee',OLD.assignee_operator_id,'to_assignee',NEW.assignee_operator_id
        );
    ELSIF NEW.due_at IS DISTINCT FROM OLD.due_at THEN
        event_name := 'due_changed';
        details_payload := jsonb_build_object('from_due_at',OLD.due_at,'to_due_at',NEW.due_at);
    ELSIF NEW.priority IS DISTINCT FROM OLD.priority THEN
        event_name := 'priority_changed';
        details_payload := jsonb_build_object('from_priority',OLD.priority,'to_priority',NEW.priority);
    ELSE
        event_name := 'blocker_changed';
        details_payload := jsonb_build_object('from_blocker',OLD.blocker,'to_blocker',NEW.blocker);
    END IF;

    INSERT INTO football_brief.creator_revision_task_events
        (task_id,event,actor_operator_id,from_lock_version,to_lock_version,details)
    VALUES (
        NEW.id,event_name,NEW.updated_by_operator_id,
        OLD.lock_version,NEW.lock_version,details_payload
    );

    IF NEW.status='completed' THEN
        UPDATE football_brief.creator_review_comments
           SET resolved_by_operator_id=NEW.updated_by_operator_id,resolved_at=now()
         WHERE id=NEW.source_comment_id AND resolved_at IS NULL;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER creator_revision_task_event_recorded
AFTER INSERT OR UPDATE ON football_brief.creator_revision_tasks
FOR EACH ROW EXECUTE FUNCTION football_brief.record_creator_revision_task_event();

CREATE OR REPLACE FUNCTION football_brief.protect_creator_revision_task_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Creator revision task events are immutable';
END;
$$;

CREATE TRIGGER creator_revision_task_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.creator_revision_task_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_creator_revision_task_event();

COMMIT;
