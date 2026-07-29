-- P111 automatic evidence enrichment and audited Super Admin factual-claim override.
-- Forward-only: existing decisions remain valid with the new columns at safe defaults.

BEGIN;

ALTER TABLE football_brief.script_review_decisions
    ADD COLUMN unsupported_claim_override boolean NOT NULL DEFAULT false,
    ADD COLUMN unsupported_claim_count integer NOT NULL DEFAULT 0 CHECK (unsupported_claim_count >= 0),
    ADD COLUMN unsupported_claim_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD CONSTRAINT script_review_unsupported_override_consistent CHECK (
        jsonb_typeof(unsupported_claim_snapshot) = 'array'
        AND (
            (unsupported_claim_override = false
             AND unsupported_claim_count = 0
             AND jsonb_array_length(unsupported_claim_snapshot) = 0)
            OR
            (unsupported_claim_override = true
             AND decision = 'approved'
             AND unsupported_claim_count > 0
             AND jsonb_array_length(unsupported_claim_snapshot) = unsupported_claim_count)
        )
    );

CREATE OR REPLACE FUNCTION football_brief.validate_script_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_version_id uuid;
    current_lock_version bigint;
    version_status text;
    version_last_editor text;
    review_brand_id uuid;
    active_policy text;
    reviewer_is_admin boolean;
    reviewer_is_super_admin boolean;
BEGIN
    SELECT sd.current_version_id, sd.lock_version, sv.status, sv.last_edited_by, mp.brand_id
      INTO current_version_id, current_lock_version, version_status, version_last_editor, review_brand_id
      FROM football_brief.script_documents sd
      JOIN football_brief.script_versions sv
        ON sv.id = NEW.script_version_id
       AND sv.script_document_id = sd.id
      JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
      JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
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

    SELECT p.policy_key INTO active_policy
      FROM football_brief.brand_review_policies p
     WHERE p.brand_id=review_brand_id AND p.active=true
     ORDER BY p.version DESC LIMIT 1;
    active_policy := COALESCE(active_policy,'independent_review_required');

    SELECT EXISTS (
        SELECT 1
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_user_roles ur ON ur.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.reviewer_operator_id
           AND ou.active=true
           AND ur.role IN ('admin','super_admin')
    ) INTO reviewer_is_admin;

    SELECT EXISTS (
        SELECT 1
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_user_roles ur ON ur.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.reviewer_operator_id
           AND ou.active=true
           AND ur.role='super_admin'
    ) INTO reviewer_is_super_admin;

    IF version_last_editor = NEW.reviewer_operator_id THEN
        IF NEW.self_review IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Independent script review is required';
        END IF;
        IF reviewer_is_admin IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Admin role is required for script self-review';
        END IF;
        IF active_policy NOT IN ('admin_self_review_allowed','independent_final_release_required') THEN
            RAISE EXCEPTION 'Brand review policy requires independent script review';
        END IF;
    ELSIF NEW.self_review = true THEN
        IF reviewer_is_admin IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Admin role is required for script self-review';
        END IF;
        IF active_policy NOT IN ('admin_self_review_allowed','independent_final_release_required') THEN
            RAISE EXCEPTION 'Brand review policy requires independent script review';
        END IF;
    END IF;

    IF NEW.review_policy_key IS DISTINCT FROM active_policy THEN
        RAISE EXCEPTION 'Script review policy version is stale';
    END IF;

    IF NEW.unsupported_claim_override = true THEN
        IF NEW.decision IS DISTINCT FROM 'approved' THEN
            RAISE EXCEPTION 'Unsupported factual claim override is valid only for approval';
        END IF;
        IF reviewer_is_super_admin IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Super Admin role is required for unsupported factual claim override';
        END IF;
        IF NEW.unsupported_claim_count <= 0
           OR jsonb_typeof(NEW.unsupported_claim_snapshot) IS DISTINCT FROM 'array'
           OR jsonb_array_length(NEW.unsupported_claim_snapshot) IS DISTINCT FROM NEW.unsupported_claim_count THEN
            RAISE EXCEPTION 'Unsupported factual claim override evidence is incomplete';
        END IF;
        IF length(btrim(COALESCE(NEW.override_reason,''))) < 3 THEN
            RAISE EXCEPTION 'Unsupported factual claim override requires an audit reason';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

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
    matching_override_total integer;
    matching_override_claim_count integer;
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
           OR NEW.generation_evidence IS DISTINCT FROM OLD.generation_evidence
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
        SELECT count(*),
               count(*) FILTER (WHERE rd.unsupported_claim_override=true),
               COALESCE(max(rd.unsupported_claim_count),0)
          INTO matching_decision_total, matching_override_total, matching_override_claim_count
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
               SELECT 1 FROM football_brief.script_scene_plan_entries sp
                WHERE sp.script_section_id = ss.id AND sp.script_version_id = NEW.id
           );
        SELECT count(*) INTO unmapped_section_total
          FROM football_brief.script_sections ss
         WHERE ss.script_version_id = NEW.id
           AND ss.section_type <> 'cta'
           AND NOT EXISTS (
               SELECT 1 FROM football_brief.script_claims sc
                WHERE sc.script_section_id = ss.id AND sc.script_version_id = NEW.id
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
               SELECT 1 FROM football_brief.script_claim_sources cs
                WHERE cs.claim_id = sc.id AND cs.script_version_id = NEW.id
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
            IF matching_override_total <> 1
               OR matching_override_claim_count < (unsupported_factual_total + unlinked_supported_total) THEN
                RAISE EXCEPTION 'Unsupported factual claims block script approval';
            END IF;
        END IF;
        IF unresolved_review_total <> 0 THEN
            RAISE EXCEPTION 'Unresolved script review actions block approval';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON COLUMN football_brief.script_review_decisions.unsupported_claim_override IS
    'True only for an approved decision by a Super Admin that explicitly accepts unsupported or unlinked factual claims.';
COMMENT ON COLUMN football_brief.script_review_decisions.unsupported_claim_snapshot IS
    'Immutable factual-claim snapshot accepted by the Super Admin at the exact reviewed script version.';

COMMIT;
