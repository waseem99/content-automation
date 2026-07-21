-- Fail-closed preset, project, shot-version, candidate-check, decision, and motion-generation integrity.

BEGIN;

CREATE TABLE football_brief.visual_project_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_project_id uuid NOT NULL UNIQUE REFERENCES football_brief.visual_projects(id) ON DELETE RESTRICT,
    decision text NOT NULL CHECK (decision IN ('approved', 'changes_requested', 'rejected')),
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    project_lock_version bigint NOT NULL CHECK (project_lock_version >= 1),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION football_brief.validate_brand_visual_preset()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.brand_visual_presets%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Brand visual presets cannot be deleted';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.version > 1 THEN
            SELECT * INTO parent_row
              FROM football_brief.brand_visual_presets bvp
             WHERE bvp.id=NEW.parent_preset_id;
            IF parent_row.id IS NULL
               OR parent_row.brand_profile_id IS DISTINCT FROM NEW.brand_profile_id
               OR parent_row.preset_key IS DISTINCT FROM NEW.preset_key
               OR parent_row.version + 1 <> NEW.version
               OR parent_row.status NOT IN ('active','retired') THEN
                RAISE EXCEPTION 'Visual preset revisions require the immediate active or retired parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('active','retired') THEN
        IF OLD.status='active' AND NEW.status='retired'
           AND NEW.brand_profile_id IS NOT DISTINCT FROM OLD.brand_profile_id
           AND NEW.preset_key IS NOT DISTINCT FROM OLD.preset_key
           AND NEW.display_name IS NOT DISTINCT FROM OLD.display_name
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_preset_id IS NOT DISTINCT FROM OLD.parent_preset_id
           AND NEW.palette IS NOT DISTINCT FROM OLD.palette
           AND NEW.subject_rules IS NOT DISTINCT FROM OLD.subject_rules
           AND NEW.environment_rules IS NOT DISTINCT FROM OLD.environment_rules
           AND NEW.camera_rules IS NOT DISTINCT FROM OLD.camera_rules
           AND NEW.lighting_rules IS NOT DISTINCT FROM OLD.lighting_rules
           AND NEW.framing_rules IS NOT DISTINCT FROM OLD.framing_rules
           AND NEW.negative_prompt IS NOT DISTINCT FROM OLD.negative_prompt
           AND NEW.exclusions IS NOT DISTINCT FROM OLD.exclusions
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
           AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Active and retired visual presets are immutable';
    END IF;
    IF NEW.brand_profile_id IS DISTINCT FROM OLD.brand_profile_id
       OR NEW.preset_key IS DISTINCT FROM OLD.preset_key
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_preset_id IS DISTINCT FROM OLD.parent_preset_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Visual preset identity is immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='active' THEN
        IF jsonb_typeof(NEW.palette) <> 'object'
           OR jsonb_typeof(NEW.subject_rules) <> 'object'
           OR jsonb_typeof(NEW.environment_rules) <> 'object'
           OR jsonb_typeof(NEW.camera_rules) <> 'object'
           OR jsonb_typeof(NEW.lighting_rules) <> 'object'
           OR jsonb_typeof(NEW.framing_rules) <> 'object'
           OR jsonb_typeof(NEW.exclusions) <> 'array'
           OR NEW.activated_at IS NULL THEN
            RAISE EXCEPTION 'Visual preset activation requires complete structured rules and timestamp';
        END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid visual preset status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER brand_visual_preset_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.brand_visual_presets
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_brand_visual_preset();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_project()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    valid_lineage_count integer;
    shot_total integer;
    approved_shot_total integer;
    decision_total integer;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Visual projects cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        SELECT count(*) INTO valid_lineage_count
          FROM football_brief.script_versions sv
          JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
          JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
          JOIN football_brief.brand_visual_presets bvp ON bvp.id=NEW.visual_preset_id
         WHERE sv.id=NEW.script_version_id
           AND sv.status='approved'
           AND sd.current_version_id=sv.id
           AND sd.portfolio_content_id=NEW.portfolio_content_id
           AND sv.basis_content_version=NEW.content_version
           AND pc.version=NEW.content_version
           AND pc.brand_profile_id=NEW.brand_profile_id
           AND bvp.brand_profile_id=NEW.brand_profile_id
           AND bvp.status='active';
        IF valid_lineage_count <> 1 THEN
            RAISE EXCEPTION 'Visual projects require the current approved script and active matching visual preset';
        END IF;
        IF NEW.provider NOT IN ('comfyui-local','comfyui-sdxl-local')
           OR NEW.external_fee_incurred OR NEW.actual_cost_usd <> 0 THEN
            RAISE EXCEPTION 'P91 visual projects must remain local and zero-cost';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.script_version_id IS DISTINCT FROM OLD.script_version_id
       OR NEW.brand_profile_id IS DISTINCT FROM OLD.brand_profile_id
       OR NEW.visual_preset_id IS DISTINCT FROM OLD.visual_preset_id
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.candidate_count IS DISTINCT FROM OLD.candidate_count
       OR NEW.external_fee_incurred IS DISTINCT FROM OLD.external_fee_incurred
       OR NEW.actual_cost_usd IS DISTINCT FROM OLD.actual_cost_usd
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Visual project identity and local provider lineage are immutable';
    END IF;
    IF NEW.lock_version <> OLD.lock_version + 1 THEN
        RAISE EXCEPTION 'Visual project updates must increment lock_version by exactly one';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='working' AND NEW.status='ready_for_review' THEN NULL;
        ELSIF OLD.status='ready_for_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN NULL;
        ELSIF OLD.status IN ('changes_requested','rejected') AND NEW.status='working' THEN NULL;
        ELSIF OLD.status='approved' AND NEW.status='superseded' THEN NULL;
        ELSE RAISE EXCEPTION 'Invalid visual project status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    IF OLD.status='working' AND NEW.status='ready_for_review' THEN
        SELECT count(*) INTO shot_total FROM football_brief.visual_shots vs WHERE vs.visual_project_id=NEW.id;
        SELECT count(*) INTO approved_shot_total FROM football_brief.visual_shots vs WHERE vs.visual_project_id=NEW.id AND vs.status='approved';
        IF shot_total=0 OR approved_shot_total<>shot_total THEN
            RAISE EXCEPTION 'Every visual shot must be independently approved before project review';
        END IF;
    END IF;
    IF OLD.status='ready_for_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN
        SELECT count(*) INTO decision_total
          FROM football_brief.visual_project_decisions vpd
         WHERE vpd.visual_project_id=NEW.id AND vpd.decision=NEW.status;
        IF decision_total<>1 THEN
            RAISE EXCEPTION 'Visual project status requires a matching exact decision';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_project_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_projects
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_project();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_continuity_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    project_status text;
    asset_valid integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual continuity references cannot be deleted'; END IF;
    SELECT vp.status INTO project_status
      FROM football_brief.visual_projects vp
     WHERE vp.id=COALESCE(NEW.visual_project_id,OLD.visual_project_id);
    IF project_status NOT IN ('working','changes_requested') THEN
        RAISE EXCEPTION 'Continuity references can change only before project review';
    END IF;
    IF TG_OP='INSERT' AND NEW.asset_id IS NOT NULL THEN
        SELECT count(*) INTO asset_valid FROM football_brief.assets a
         WHERE a.id=NEW.asset_id AND a.asset_type='image' AND a.lifecycle_status='approved';
        IF asset_valid<>1 THEN RAISE EXCEPTION 'Continuity references require approved image assets'; END IF;
    END IF;
    IF NEW.reference_fingerprint !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'Continuity reference fingerprint is invalid'; END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW.visual_project_id IS DISTINCT FROM OLD.visual_project_id
           OR NEW.reference_key IS DISTINCT FROM OLD.reference_key
           OR NEW.reference_type IS DISTINCT FROM OLD.reference_type
           OR NEW.asset_id IS DISTINCT FROM OLD.asset_id
           OR NEW.reference_fingerprint IS DISTINCT FROM OLD.reference_fingerprint
           OR NEW.description IS DISTINCT FROM OLD.description
           OR NEW.attributes IS DISTINCT FROM OLD.attributes
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR OLD.active=false OR NEW.active<>false THEN
            RAISE EXCEPTION 'Continuity references are immutable except one-time deactivation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_continuity_reference_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.visual_continuity_references
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_continuity_reference();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_candidate_check()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Visual candidate checks are immutable'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_candidate_checks_immutable
BEFORE UPDATE OR DELETE ON football_brief.visual_candidate_checks
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_candidate_check();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_candidate_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_version uuid;
    current_lock bigint;
    version_editor text;
    candidate_creator text;
    candidate_status text;
    checks_status text;
    required_count integer;
    failed_count integer;
    unresolved_count integer;
BEGIN
    SELECT vs.current_version_id,vs.lock_version,vsv.last_edited_by,vc.created_by,vc.status,vc.checks_status
      INTO current_version,current_lock,version_editor,candidate_creator,candidate_status,checks_status
      FROM football_brief.visual_shots vs
      JOIN football_brief.visual_shot_versions vsv ON vsv.id=NEW.visual_shot_version_id AND vsv.visual_shot_id=vs.id
      JOIN football_brief.visual_candidates vc ON vc.id=NEW.visual_candidate_id AND vc.visual_shot_version_id=vsv.id
     WHERE vs.id=NEW.visual_shot_id AND vs.visual_project_id=NEW.visual_project_id
     FOR UPDATE OF vs,vsv,vc;
    IF current_version IS DISTINCT FROM NEW.visual_shot_version_id THEN RAISE EXCEPTION 'Stale visual shot versions cannot be decided'; END IF;
    IF current_lock IS DISTINCT FROM NEW.shot_lock_version THEN RAISE EXCEPTION 'Visual shot decision lock is stale'; END IF;
    IF NEW.reviewer_operator_id IN (version_editor,candidate_creator) THEN RAISE EXCEPTION 'Independent visual candidate review is required'; END IF;
    IF candidate_status<>'generated' THEN RAISE EXCEPTION 'Only generated visual candidates can be decided'; END IF;
    IF NEW.decision='selected' THEN
        SELECT count(DISTINCT vcc.check_type),count(*) FILTER (WHERE vcc.status<>'pass')
          INTO required_count,failed_count
          FROM football_brief.visual_candidate_checks vcc
         WHERE vcc.visual_candidate_id=NEW.visual_candidate_id;
        SELECT count(*) INTO unresolved_count
          FROM football_brief.visual_shot_review_actions vsra
         WHERE vsra.visual_shot_version_id=NEW.visual_shot_version_id
           AND vsra.resolved_at IS NULL;
        IF checks_status<>'pass' OR required_count<>10 OR failed_count<>0 THEN
            RAISE EXCEPTION 'Selected visual candidates require all ten passing checks';
        END IF;
        IF unresolved_count<>0 THEN RAISE EXCEPTION 'Unresolved visual shot review actions block selection'; END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_candidate_decision_valid
BEFORE INSERT ON football_brief.visual_candidate_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_candidate_decision();

CREATE OR REPLACE FUNCTION football_brief.apply_visual_candidate_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.decision='selected' THEN
        UPDATE football_brief.visual_candidates SET status='superseded'
         WHERE visual_shot_version_id=NEW.visual_shot_version_id AND status='selected';
        UPDATE football_brief.visual_candidates SET status='selected' WHERE id=NEW.visual_candidate_id;
        UPDATE football_brief.visual_shot_versions SET status='selected',decided_at=now() WHERE id=NEW.visual_shot_version_id;
        UPDATE football_brief.visual_shots
           SET selected_candidate_id=NEW.visual_candidate_id,status='approved',lock_version=lock_version+1
         WHERE id=NEW.visual_shot_id AND lock_version=NEW.shot_lock_version;
        INSERT INTO football_brief.visual_project_events
            (visual_project_id,visual_shot_id,visual_shot_version_id,visual_candidate_id,event,actor,details)
        VALUES (NEW.visual_project_id,NEW.visual_shot_id,NEW.visual_shot_version_id,NEW.visual_candidate_id,'candidate_selected',NEW.reviewer_operator_id,jsonb_build_object('decision_id',NEW.id));
    ELSE
        UPDATE football_brief.visual_candidates SET status='rejected' WHERE id=NEW.visual_candidate_id;
        INSERT INTO football_brief.visual_project_events
            (visual_project_id,visual_shot_id,visual_shot_version_id,visual_candidate_id,event,actor,details)
        VALUES (NEW.visual_project_id,NEW.visual_shot_id,NEW.visual_shot_version_id,NEW.visual_candidate_id,'candidate_rejected',NEW.reviewer_operator_id,jsonb_build_object('decision_id',NEW.id));
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_candidate_decision_apply
AFTER INSERT ON football_brief.visual_candidate_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_visual_candidate_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_candidate_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Visual candidate decisions are immutable'; END;
$$;
CREATE TRIGGER visual_candidate_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.visual_candidate_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_candidate_decision();

CREATE OR REPLACE FUNCTION football_brief.validate_visual_project_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    project_status text;
    current_lock bigint;
    last_editor text;
    shot_total integer;
    approved_shot_total integer;
BEGIN
    SELECT vp.status,vp.lock_version,vp.last_edited_by
      INTO project_status,current_lock,last_editor
      FROM football_brief.visual_projects vp WHERE vp.id=NEW.visual_project_id FOR UPDATE;
    IF project_status<>'ready_for_review' THEN RAISE EXCEPTION 'Visual project must be ready for review'; END IF;
    IF current_lock IS DISTINCT FROM NEW.project_lock_version THEN RAISE EXCEPTION 'Visual project decision lock is stale'; END IF;
    IF last_editor=NEW.reviewer_operator_id THEN RAISE EXCEPTION 'Independent visual project review is required'; END IF;
    IF NEW.decision='approved' THEN
        SELECT count(*),count(*) FILTER (WHERE vs.status='approved') INTO shot_total,approved_shot_total
          FROM football_brief.visual_shots vs WHERE vs.visual_project_id=NEW.visual_project_id;
        IF shot_total=0 OR approved_shot_total<>shot_total THEN RAISE EXCEPTION 'All visual shots must be approved'; END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_project_decision_valid
BEFORE INSERT ON football_brief.visual_project_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_visual_project_decision();

CREATE OR REPLACE FUNCTION football_brief.apply_visual_project_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE football_brief.visual_projects
       SET status=NEW.decision,decided_at=now(),lock_version=lock_version+1
     WHERE id=NEW.visual_project_id AND lock_version=NEW.project_lock_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'Visual project decision could not advance current project'; END IF;
    INSERT INTO football_brief.visual_project_events
        (visual_project_id,event,actor,details)
    VALUES (NEW.visual_project_id,
            CASE NEW.decision WHEN 'approved' THEN 'project_approved' WHEN 'changes_requested' THEN 'project_changes_requested' ELSE 'project_rejected' END,
            NEW.reviewer_operator_id,jsonb_build_object('decision_id',NEW.id,'rationale',NEW.rationale));
    RETURN NEW;
END;
$$;

CREATE TRIGGER visual_project_decision_apply
AFTER INSERT ON football_brief.visual_project_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_visual_project_decision();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_project_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Visual project decisions are immutable'; END;
$$;
CREATE TRIGGER visual_project_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.visual_project_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_project_decision();

CREATE OR REPLACE FUNCTION football_brief.require_selected_visual_for_motion_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    active_project_id uuid;
    candidate_text text;
    requested_candidate_id uuid;
    valid_candidate_count integer;
BEGIN
    IF NEW.job_type NOT IN ('preview','premium_clip') THEN RETURN NEW; END IF;
    SELECT vp.id INTO active_project_id
      FROM football_brief.visual_projects vp
     WHERE vp.portfolio_content_id=NEW.portfolio_content_id
       AND vp.content_version=NEW.content_version
       AND vp.status IN ('working','ready_for_review','approved','changes_requested','rejected')
     ORDER BY vp.created_at DESC LIMIT 1;
    IF active_project_id IS NULL THEN RETURN NEW; END IF;
    candidate_text:=NEW.input_payload->>'visual_candidate_id';
    IF candidate_text IS NULL OR candidate_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN
        RAISE EXCEPTION 'Motion jobs require a selected visual_candidate_id';
    END IF;
    requested_candidate_id:=candidate_text::uuid;
    SELECT count(*) INTO valid_candidate_count
      FROM football_brief.visual_candidates vc
      JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
      JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
      JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
     WHERE vc.id=requested_candidate_id
       AND vc.status='selected' AND vc.checks_status='pass'
       AND vs.selected_candidate_id=vc.id AND vs.status='approved'
       AND vp.id=active_project_id AND vp.status='approved'
       AND NOT EXISTS (
           SELECT 1 FROM football_brief.visual_candidate_checks vcc
            WHERE vcc.visual_candidate_id=vc.id AND vcc.status<>'pass'
       );
    IF valid_candidate_count<>1 THEN RAISE EXCEPTION 'Motion generation is blocked until continuity review passes'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_visual_motion_gate
BEFORE INSERT ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.require_selected_visual_for_motion_job();

CREATE OR REPLACE FUNCTION football_brief.protect_visual_project_event()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Visual project events are immutable'; END;
$$;
CREATE TRIGGER visual_project_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.visual_project_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_visual_project_event();

COMMIT;