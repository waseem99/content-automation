-- Exact scene ownership, immediate prompt revisions, local keyframe lineage, check aggregation, and review-action sealing.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_visual_shot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    project_script_version uuid;
    scene_script_version uuid;
    new_version_number integer;
    old_version_number integer;
    new_parent uuid;
    new_version_status text;
    candidate_version uuid;
    candidate_status text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual shots cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT vp.script_version_id INTO project_script_version
          FROM football_brief.visual_projects vp WHERE vp.id=NEW.visual_project_id;
        SELECT sspe.script_version_id INTO scene_script_version
          FROM football_brief.script_scene_plan_entries sspe WHERE sspe.id=NEW.scene_plan_entry_id;
        IF project_script_version IS DISTINCT FROM scene_script_version THEN
            RAISE EXCEPTION 'Visual shot scene must belong to the exact approved project script';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.visual_project_id IS DISTINCT FROM OLD.visual_project_id
       OR NEW.scene_plan_entry_id IS DISTINCT FROM OLD.scene_plan_entry_id
       OR NEW.sequence IS DISTINCT FROM OLD.sequence
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Visual shot identity is immutable';
    END IF;
    IF NEW.lock_version<>OLD.lock_version+1 THEN
        RAISE EXCEPTION 'Visual shot updates must increment lock_version by exactly one';
    END IF;
    IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id THEN
        SELECT vsv.version,vsv.parent_version_id,vsv.status
          INTO new_version_number,new_parent,new_version_status
          FROM football_brief.visual_shot_versions vsv
         WHERE vsv.id=NEW.current_version_id AND vsv.visual_shot_id=NEW.id;
        SELECT vsv.version INTO old_version_number
          FROM football_brief.visual_shot_versions vsv WHERE vsv.id=OLD.current_version_id;
        IF OLD.status NOT IN ('changes_requested','rejected')
           OR NEW.status<>'working'
           OR new_version_status<>'working'
           OR new_parent IS DISTINCT FROM OLD.current_version_id
           OR new_version_number<>old_version_number+1 THEN
            RAISE EXCEPTION 'Visual shot revisions must be immediate working children of a reviewed version';
        END IF;
        IF NEW.selected_candidate_id IS NOT NULL THEN RAISE EXCEPTION 'A revised visual shot cannot retain the old selected candidate'; END IF;
    END IF;
    IF NEW.selected_candidate_id IS DISTINCT FROM OLD.selected_candidate_id AND NEW.selected_candidate_id IS NOT NULL THEN
        SELECT vc.visual_shot_version_id,vc.status INTO candidate_version,candidate_status
          FROM football_brief.visual_candidates vc WHERE vc.id=NEW.selected_candidate_id;
        IF candidate_version IS DISTINCT FROM NEW.current_version_id OR candidate_status<>'selected' THEN
            RAISE EXCEPTION 'Visual shot selection must use a selected candidate from its current version';
        END IF;
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='working' AND NEW.status='candidates_ready' THEN NULL;
        ELSIF OLD.status='candidates_ready' AND NEW.status IN ('approved','changes_requested','rejected') THEN NULL;
        ELSIF OLD.status IN ('changes_requested','rejected') AND NEW.status='working' THEN NULL;
        ELSE RAISE EXCEPTION 'Invalid visual shot status transition from % to %',OLD.status,NEW.status;
        END IF;
    END IF;
    IF NEW.status='approved' AND NEW.selected_candidate_id IS NULL THEN
        RAISE EXCEPTION 'Approved visual shots require a selected candidate';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_shot_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_shots
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_shot();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_shot_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    project_status text;
    parent_row football_brief.visual_shot_versions%ROWTYPE;
    candidate_total integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual shot versions cannot be deleted'; END IF;
    SELECT vp.status INTO project_status
      FROM football_brief.visual_shots vs
      JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
     WHERE vs.id=COALESCE(NEW.visual_shot_id,OLD.visual_shot_id);
    IF TG_OP='INSERT' THEN
        IF project_status NOT IN ('working','changes_requested') THEN
            RAISE EXCEPTION 'Visual shot versions require a writable visual project';
        END IF;
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.visual_shot_versions vsv
             WHERE vsv.id=NEW.parent_version_id;
            IF parent_row.id IS NULL
               OR parent_row.visual_shot_id IS DISTINCT FROM NEW.visual_shot_id
               OR parent_row.version+1<>NEW.version
               OR parent_row.status NOT IN ('selected','changes_requested','rejected') THEN
                RAISE EXCEPTION 'Visual prompt revisions require the immediate reviewed parent';
            END IF;
        END IF;
        IF jsonb_typeof(NEW.prompt_components)<>'object'
           OR NOT (NEW.prompt_components ?& ARRAY['subject','action','environment','camera','lighting','palette','framing','exclusions']) THEN
            RAISE EXCEPTION 'Visual shot prompt components are incomplete';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.visual_shot_id IS DISTINCT FROM OLD.visual_shot_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Visual shot version identity is immutable';
    END IF;
    IF OLD.status IN ('selected','changes_requested','rejected','superseded') THEN
        RAISE EXCEPTION 'Reviewed visual shot versions are immutable';
    END IF;
    IF OLD.status='candidates_ready' THEN
        IF NEW.compiled_prompt IS DISTINCT FROM OLD.compiled_prompt
           OR NEW.negative_prompt IS DISTINCT FROM OLD.negative_prompt
           OR NEW.prompt_components IS DISTINCT FROM OLD.prompt_components
           OR NEW.reference_snapshot IS DISTINCT FROM OLD.reference_snapshot
           OR NEW.width IS DISTINCT FROM OLD.width
           OR NEW.height IS DISTINCT FROM OLD.height
           OR NEW.aspect_ratio IS DISTINCT FROM OLD.aspect_ratio
           OR NEW.candidate_target_count IS DISTINCT FROM OLD.candidate_target_count
           OR NEW.revision_reason IS DISTINCT FROM OLD.revision_reason
           OR NEW.last_edited_by IS DISTINCT FROM OLD.last_edited_by THEN
            RAISE EXCEPTION 'Candidate-ready visual prompts are sealed';
        END IF;
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='working' AND NEW.status='candidates_ready' THEN
            SELECT count(*) INTO candidate_total FROM football_brief.visual_candidates vc
             WHERE vc.visual_shot_version_id=NEW.id;
            IF candidate_total<NEW.candidate_target_count THEN
                RAISE EXCEPTION 'Visual shot version requires the full candidate set';
            END IF;
        ELSIF OLD.status='candidates_ready' AND NEW.status IN ('selected','changes_requested','rejected') THEN NULL;
        ELSE RAISE EXCEPTION 'Invalid visual shot version status transition from % to %',OLD.status,NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_shot_version_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_shot_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_shot_version();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_candidate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    project_row record;
    current_version uuid;
    job_valid integer;
    asset_valid integer;
    check_total integer;
    nonpass_total integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual candidates cannot be deleted'; END IF;
    SELECT vp.id AS project_id,vp.portfolio_content_id,vp.content_version,vp.provider,vp.model_id,vp.status,
           vs.current_version_id
      INTO project_row
      FROM football_brief.visual_shot_versions vsv
      JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
      JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
     WHERE vsv.id=COALESCE(NEW.visual_shot_version_id,OLD.visual_shot_version_id);
    IF TG_OP='INSERT' THEN
        IF project_row.status NOT IN ('working','changes_requested')
           OR project_row.current_version_id IS DISTINCT FROM NEW.visual_shot_version_id THEN
            RAISE EXCEPTION 'Visual candidates require the current version of a writable project';
        END IF;
        IF NEW.provider IS DISTINCT FROM project_row.provider OR NEW.model_id IS DISTINCT FROM project_row.model_id
           OR NEW.external_fee_incurred OR NEW.actual_cost_usd<>0 THEN
            RAISE EXCEPTION 'P91 candidates must use the pinned local zero-cost provider';
        END IF;
        IF NEW.generation_job_id IS NOT NULL THEN
            SELECT count(*) INTO job_valid FROM football_brief.generation_jobs gj
             WHERE gj.id=NEW.generation_job_id
               AND gj.portfolio_content_id=project_row.portfolio_content_id
               AND gj.content_version=project_row.content_version
               AND gj.job_type='keyframe'
               AND gj.provider=NEW.provider AND gj.model_id=NEW.model_id
               AND gj.input_payload->>'visual_project_id'=project_row.project_id::text
               AND gj.input_payload->>'visual_shot_version_id'=NEW.visual_shot_version_id::text
               AND gj.input_payload->>'seed'=NEW.seed::text;
            IF job_valid<>1 THEN RAISE EXCEPTION 'Visual candidate generation job lineage is invalid'; END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.visual_shot_version_id IS DISTINCT FROM OLD.visual_shot_version_id
       OR NEW.ordinal IS DISTINCT FROM OLD.ordinal
       OR NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.seed IS DISTINCT FROM OLD.seed
       OR NEW.width IS DISTINCT FROM OLD.width
       OR NEW.height IS DISTINCT FROM OLD.height
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.prompt_snapshot IS DISTINCT FROM OLD.prompt_snapshot
       OR NEW.negative_prompt_snapshot IS DISTINCT FROM OLD.negative_prompt_snapshot
       OR NEW.reference_snapshot IS DISTINCT FROM OLD.reference_snapshot
       OR NEW.actual_cost_usd IS DISTINCT FROM OLD.actual_cost_usd
       OR NEW.external_fee_incurred IS DISTINCT FROM OLD.external_fee_incurred
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Visual candidate identity and generation lineage are immutable';
    END IF;
    IF OLD.status IN ('selected','rejected','superseded','failed') THEN
        RAISE EXCEPTION 'Terminal visual candidates are immutable';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='queued' AND NEW.status IN ('generated','failed') THEN NULL;
        ELSIF OLD.status='generated' AND NEW.status IN ('selected','rejected','superseded') THEN NULL;
        ELSE RAISE EXCEPTION 'Invalid visual candidate status transition from % to %',OLD.status,NEW.status;
        END IF;
    END IF;
    IF NEW.status='generated' THEN
        SELECT count(*) INTO asset_valid FROM football_brief.assets a
         WHERE a.id=NEW.asset_id AND a.asset_type='image' AND a.lifecycle_status='approved';
        IF asset_valid<>1 OR jsonb_typeof(NEW.provenance)<>'object' OR NEW.provenance='{}'::jsonb THEN
            RAISE EXCEPTION 'Generated visual candidates require an approved image asset and provenance';
        END IF;
    END IF;
    IF NEW.checks_status IS DISTINCT FROM OLD.checks_status THEN
        IF OLD.checks_status<>'pending' OR NEW.checks_status NOT IN ('pass','fail') THEN
            RAISE EXCEPTION 'Invalid visual candidate check-status transition';
        END IF;
        SELECT count(DISTINCT vcc.check_type),count(*) FILTER (WHERE vcc.status<>'pass')
          INTO check_total,nonpass_total FROM football_brief.visual_candidate_checks vcc
         WHERE vcc.visual_candidate_id=NEW.id;
        IF check_total<>10 THEN RAISE EXCEPTION 'All ten visual candidate checks are required'; END IF;
        IF (NEW.checks_status='pass' AND nonpass_total<>0) OR (NEW.checks_status='fail' AND nonpass_total=0) THEN
            RAISE EXCEPTION 'Visual candidate aggregate check status does not match check evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_candidate_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_candidate();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_candidate_check_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE candidate_status text;
BEGIN
    SELECT vc.status INTO candidate_status FROM football_brief.visual_candidates vc WHERE vc.id=NEW.visual_candidate_id;
    IF candidate_status<>'generated' THEN RAISE EXCEPTION 'Checks require a generated visual candidate'; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER visual_candidate_check_insert_valid
BEFORE INSERT ON football_brief.visual_candidate_checks
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_candidate_check_insert();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_shot_review_action()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE current_version uuid; shot_status text; candidate_version uuid;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual shot review actions cannot be deleted'; END IF;
    SELECT vs.current_version_id,vs.status INTO current_version,shot_status
      FROM football_brief.visual_shots vs WHERE vs.id=COALESCE(NEW.visual_shot_id,OLD.visual_shot_id);
    IF TG_OP='INSERT' THEN
        IF current_version IS DISTINCT FROM NEW.visual_shot_version_id OR shot_status NOT IN ('candidates_ready','changes_requested') THEN
            RAISE EXCEPTION 'Visual review actions require the current candidate-ready shot version';
        END IF;
        IF NEW.visual_candidate_id IS NOT NULL THEN
            SELECT vc.visual_shot_version_id INTO candidate_version FROM football_brief.visual_candidates vc WHERE vc.id=NEW.visual_candidate_id;
            IF candidate_version IS DISTINCT FROM NEW.visual_shot_version_id THEN RAISE EXCEPTION 'Visual review action candidate belongs to another version'; END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.resolved_at IS NOT NULL
       OR NEW.visual_project_id IS DISTINCT FROM OLD.visual_project_id
       OR NEW.visual_shot_id IS DISTINCT FROM OLD.visual_shot_id
       OR NEW.visual_shot_version_id IS DISTINCT FROM OLD.visual_shot_version_id
       OR NEW.visual_candidate_id IS DISTINCT FROM OLD.visual_candidate_id
       OR NEW.action_type IS DISTINCT FROM OLD.action_type
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.suggested_value IS DISTINCT FROM OLD.suggested_value
       OR NEW.author_operator_id IS DISTINCT FROM OLD.author_operator_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.resolved_at IS NULL OR NEW.resolved_by_operator_id IS NULL THEN
        RAISE EXCEPTION 'Visual shot review actions are immutable except one-time resolution';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER visual_shot_review_action_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_shot_review_actions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_shot_review_action();

COMMIT;