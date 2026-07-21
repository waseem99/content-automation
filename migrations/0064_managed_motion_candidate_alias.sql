-- Preserve the P91 continuity gate while accepting P94's explicit selected_candidate_id alias.

BEGIN;

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
    candidate_text:=COALESCE(
        NEW.input_payload->>'visual_candidate_id',
        NEW.input_payload->>'selected_candidate_id'
    );
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

COMMIT;
