-- Fail-closed script version, duration, claim, source, and review integrity.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_script_document()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    workflow_content_id uuid;
BEGIN
    SELECT pw.portfolio_content_id INTO workflow_content_id
      FROM football_brief.production_workflows pw
     WHERE pw.id = NEW.production_workflow_id;
    IF workflow_content_id IS DISTINCT FROM NEW.portfolio_content_id THEN
        RAISE EXCEPTION 'Script document workflow must belong to its content item';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
           OR NEW.production_workflow_id IS DISTINCT FROM OLD.production_workflow_id
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Script document identity is immutable';
        END IF;
        IF NEW.lock_version <> OLD.lock_version + 1 THEN
            RAISE EXCEPTION 'Script document updates must increment lock_version by exactly one';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER script_document_valid
BEFORE INSERT OR UPDATE ON football_brief.script_documents
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_script_document();

CREATE OR REPLACE FUNCTION football_brief.protect_script_child_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_version_id uuid;
    parent_status text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_version_id := OLD.script_version_id;
    ELSE
        target_version_id := NEW.script_version_id;
    END IF;

    SELECT sv.status INTO parent_status
      FROM football_brief.script_versions sv
     WHERE sv.id = target_version_id;

    IF parent_status IS DISTINCT FROM 'working' THEN
        RAISE EXCEPTION 'Submitted script child evidence is immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER script_sections_working_only
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_sections
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_child_evidence();

CREATE TRIGGER script_scene_plan_working_only
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_scene_plan_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_child_evidence();

CREATE TRIGGER script_claims_working_only
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_claims
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_child_evidence();

CREATE TRIGGER script_sources_working_only
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_sources
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_child_evidence();

CREATE TRIGGER script_claim_sources_working_only
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.script_claim_sources
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_script_child_evidence();

CREATE OR REPLACE FUNCTION football_brief.validate_script_version_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    section_total integer;
    section_words integer;
    section_duration numeric(10,3);
    allowed_duration numeric(10,3);
    missing_scene_total integer;
    unmapped_section_total integer;
    unsupported_factual_total integer;
    unlinked_supported_total integer;
    unresolved_review_total integer;
    matching_decision_total integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Script versions cannot be deleted';
    END IF;

    IF NEW.script_document_id IS DISTINCT FROM OLD.script_document_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
       OR NEW.basis_content_version IS DISTINCT FROM OLD.basis_content_version
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Script version identity is immutable';
    END IF;

    IF OLD.status IN ('approved', 'changes_requested', 'rejected', 'superseded') THEN
        RAISE EXCEPTION 'Terminal script versions are immutable';
    END IF;

    IF OLD.status = 'in_review' THEN
        IF NEW.platform IS DISTINCT FROM OLD.platform
           OR NEW.format IS DISTINCT FROM OLD.format
           OR NEW.language IS DISTINCT FROM OLD.language
           OR NEW.target_duration_seconds IS DISTINCT FROM OLD.target_duration_seconds
           OR NEW.words_per_minute IS DISTINCT FROM OLD.words_per_minute
           OR NEW.word_count IS DISTINCT FROM OLD.word_count
           OR NEW.estimated_duration_seconds IS DISTINCT FROM OLD.estimated_duration_seconds
           OR NEW.duration_tolerance_percent IS DISTINCT FROM OLD.duration_tolerance_percent
           OR NEW.hook_text IS DISTINCT FROM OLD.hook_text
           OR NEW.cta_text IS DISTINCT FROM OLD.cta_text
           OR NEW.full_text IS DISTINCT FROM OLD.full_text
           OR NEW.content_fingerprint IS DISTINCT FROM OLD.content_fingerprint
           OR NEW.adapter_mode IS DISTINCT FROM OLD.adapter_mode
           OR NEW.local_model_id IS DISTINCT FROM OLD.local_model_id
           OR NEW.last_edited_by IS DISTINCT FROM OLD.last_edited_by
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
            RAISE EXCEPTION 'Submitted script versions are immutable';
        END IF;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'working' AND NEW.status = 'in_review' THEN
            NULL;
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid script version status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF OLD.status = 'working' AND NEW.status = 'in_review' THEN
        SELECT count(*), COALESCE(sum(ss.word_count), 0),
               COALESCE(sum(ss.estimated_duration_seconds), 0)
          INTO section_total, section_words, section_duration
          FROM football_brief.script_sections ss
         WHERE ss.script_version_id = NEW.id;
        IF section_total = 0 OR section_words <> NEW.word_count THEN
            RAISE EXCEPTION 'Submitted script word count must match its sections';
        END IF;
        IF abs(section_duration - NEW.estimated_duration_seconds) > 0.01 THEN
            RAISE EXCEPTION 'Submitted script duration must match its sections';
        END IF;
    END IF;

    IF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
        SELECT count(*) INTO matching_decision_total
          FROM football_brief.script_review_decisions rd
         WHERE rd.script_version_id = NEW.id
           AND rd.decision = NEW.status;
        IF matching_decision_total <> 1 THEN
            RAISE EXCEPTION 'Script decision must match the exact submitted version and status';
        END IF;
    END IF;

    IF OLD.status = 'in_review' AND NEW.status = 'approved' THEN
        SELECT COALESCE(sum(ss.word_count), 0),
               COALESCE(sum(ss.estimated_duration_seconds), 0)
          INTO section_words, section_duration
          FROM football_brief.script_sections ss
         WHERE ss.script_version_id = NEW.id;

        allowed_duration := NEW.target_duration_seconds *
            (1 + (NEW.duration_tolerance_percent / 100));

        SELECT count(*) INTO missing_scene_total
          FROM football_brief.script_sections ss
         WHERE ss.script_version_id = NEW.id
           AND NOT EXISTS (
               SELECT 1
                 FROM football_brief.script_scene_plan_entries sp
                WHERE sp.script_section_id = ss.id
                  AND sp.script_version_id = NEW.id
           );

        SELECT count(*) INTO unmapped_section_total
          FROM football_brief.script_sections ss
         WHERE ss.script_version_id = NEW.id
           AND ss.section_type <> 'cta'
           AND NOT EXISTS (
               SELECT 1
                 FROM football_brief.script_claims sc
                WHERE sc.script_section_id = ss.id
                  AND sc.script_version_id = NEW.id
           );

        SELECT count(*) INTO unsupported_factual_total
          FROM football_brief.script_claims sc
         WHERE sc.script_version_id = NEW.id
           AND sc.claim_type = 'factual'
           AND sc.support_status <> 'supported';

        SELECT count(*) INTO unlinked_supported_total
          FROM football_brief.script_claims sc
         WHERE sc.script_version_id = NEW.id
           AND sc.claim_type = 'factual'
           AND sc.support_status = 'supported'
           AND NOT EXISTS (
               SELECT 1
                 FROM football_brief.script_claim_sources cs
                WHERE cs.claim_id = sc.id
                  AND cs.script_version_id = NEW.id
                  AND cs.support_type IN ('direct', 'corroborating')
           );

        SELECT count(*) INTO unresolved_review_total
          FROM football_brief.script_review_actions ra
         WHERE ra.script_version_id = NEW.id
           AND ra.action_type IN ('inline_edit', 'factual_query', 'source_request', 'tone_change')
           AND ra.resolved_at IS NULL;

        IF section_words = 0 OR section_words <> NEW.word_count THEN
            RAISE EXCEPTION 'Approved script word count must match its sections';
        END IF;
        IF abs(section_duration - NEW.estimated_duration_seconds) > 0.01 THEN
            RAISE EXCEPTION 'Approved script duration must match its sections';
        END IF;
        IF NEW.estimated_duration_seconds > allowed_duration THEN
            RAISE EXCEPTION 'Script narration duration exceeds the approved tolerance';
        END IF;
        IF missing_scene_total <> 0 THEN
            RAISE EXCEPTION 'Every approved script section requires a scene-plan entry';
        END IF;
        IF unmapped_section_total <> 0 THEN
            RAISE EXCEPTION 'Every final narration paragraph requires a claim mapping';
        END IF;
        IF unsupported_factual_total <> 0 OR unlinked_supported_total <> 0 THEN
            RAISE EXCEPTION 'Unsupported factual claims block script approval';
        END IF;
        IF unresolved_review_total <> 0 THEN
            RAISE EXCEPTION 'Unresolved script review actions block approval';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER script_version_transition_valid
BEFORE UPDATE OR DELETE ON football_brief.script_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_script_version_transition();

COMMIT;
