-- Require independent, brand-scoped role signers and validate passed content evidence against canonical records.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_signoff()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actual_role boolean;
    item_count integer;
    passed_count integer;
    blocking_defects integer;
    missing_operations integer;
    prior_operator_count integer;
    missing_brand_assignments integer:=0;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Acceptance sign-offs are append-only'; END IF;
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.operator_id AND ou.active AND our.role=NEW.signoff_role
    ) INTO actual_role;
    IF NOT actual_role THEN RAISE EXCEPTION 'Sign-off operator must hold the recorded role'; END IF;
    SELECT count(*) INTO prior_operator_count
      FROM football_brief.acceptance_pilot_signoffs
     WHERE pilot_id=NEW.pilot_id AND operator_id=NEW.operator_id;
    IF prior_operator_count<>0 THEN
        RAISE EXCEPTION 'Admin, Reviewer, and Publisher sign-offs require distinct operators';
    END IF;
    IF NEW.signoff_role<>'admin' THEN
        SELECT count(*) INTO missing_brand_assignments
          FROM (
              SELECT DISTINCT brand_id
                FROM football_brief.acceptance_pilot_items
               WHERE pilot_id=NEW.pilot_id
          ) pilot_brand
         WHERE NOT EXISTS (
             SELECT 1
               FROM football_brief.operator_users ou
               JOIN football_brief.operator_brand_assignments oba
                 ON oba.operator_user_id=ou.id
              WHERE ou.operator_id=NEW.operator_id
                AND ou.active
                AND oba.brand_id=pilot_brand.brand_id
         );
        IF missing_brand_assignments<>0 THEN
            RAISE EXCEPTION 'Reviewer and Publisher sign-offs require assignment to every pilot brand';
        END IF;
    END IF;
    SELECT count(*),count(*) FILTER (WHERE status='passed') INTO item_count,passed_count
      FROM football_brief.acceptance_pilot_items WHERE pilot_id=NEW.pilot_id;
    SELECT count(*) INTO blocking_defects FROM football_brief.acceptance_pilot_defects
     WHERE pilot_id=NEW.pilot_id AND severity IN ('major','critical') AND status='open';
    WITH required(category) AS (
        VALUES ('backup_restore'),('worker_restart'),('runbook_validation')
    )
    SELECT count(*) INTO missing_operations
      FROM required r
     WHERE NOT EXISTS (
         SELECT 1 FROM football_brief.acceptance_pilot_evidence ape
         JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
          WHERE api.pilot_id=NEW.pilot_id AND ape.category=r.category AND ape.passed
     );
    IF item_count<>4 OR passed_count<>4 OR blocking_defects<>0 OR missing_operations<>0 THEN
        RAISE EXCEPTION 'Sign-off requires four passed items, operations evidence, and no blocking defect';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_live_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_row football_brief.acceptance_pilot_items%ROWTYPE;
    release_row football_brief.final_releases%ROWTYPE;
    signoff_count integer;
    is_publisher boolean;
    assigned_to_brand boolean;
    blocking_defects integer;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Live delivery evidence is append-only'; END IF;
    SELECT * INTO item_row FROM football_brief.acceptance_pilot_items WHERE id=NEW.pilot_item_id;
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.final_release_id;
    SELECT count(*) INTO signoff_count FROM football_brief.acceptance_pilot_signoffs
     WHERE pilot_id=NEW.pilot_id AND decision='approved';
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.recorded_by AND ou.active AND our.role='publisher'
    ) INTO is_publisher;
    SELECT EXISTS (
        SELECT 1
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_brand_assignments oba ON oba.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.recorded_by
           AND ou.active
           AND oba.brand_id=item_row.brand_id
    ) INTO assigned_to_brand;
    SELECT count(*) INTO blocking_defects FROM football_brief.acceptance_pilot_defects
     WHERE pilot_id=NEW.pilot_id AND severity IN ('major','critical') AND status='open';
    IF item_row.id IS NULL OR item_row.pilot_id IS DISTINCT FROM NEW.pilot_id
       OR NOT item_row.live_delivery_evidence_required
       OR release_row.id IS NULL OR release_row.status<>'approved'
       OR release_row.portfolio_content_id IS DISTINCT FROM item_row.portfolio_content_id
       OR release_row.content_version IS DISTINCT FROM item_row.content_version
       OR signoff_count<>3 OR NOT is_publisher OR NOT assigned_to_brand OR blocking_defects<>0 THEN
        RAISE EXCEPTION 'Live result evidence requires exact approved release, three sign-offs, assigned Publisher, and no blocking defects';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_content_subject()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_row football_brief.acceptance_pilot_items%ROWTYPE;
    subject_uuid uuid;
    valid_subject boolean:=false;
BEGIN
    IF NOT NEW.passed OR NEW.category IN ('backup_restore','worker_restart','runbook_validation','role_assignment','source_evidence','routing_explanation','renderer_lineage','production_economics') THEN
        RETURN NEW;
    END IF;
    SELECT * INTO item_row FROM football_brief.acceptance_pilot_items WHERE id=NEW.pilot_item_id;
    IF item_row.id IS NULL THEN RAISE EXCEPTION 'Acceptance evidence requires a pilot item'; END IF;
    BEGIN
        subject_uuid:=NEW.subject_id::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'Passed content evidence requires a canonical UUID subject';
    END;

    CASE NEW.category
      WHEN 'brand_profile' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.brand_profiles bp
            JOIN football_brief.portfolio_content pc ON pc.brand_profile_id=bp.id
             WHERE bp.id=subject_uuid AND pc.id=item_row.portfolio_content_id
               AND bp.brand_id=item_row.brand_id AND bp.status IN ('active','retired')
        ) INTO valid_subject;
      WHEN 'narration_preset' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.brand_narration_presets bnp
            JOIN football_brief.portfolio_content pc ON pc.narration_preset_id=bnp.id
            JOIN football_brief.brand_profiles bp ON bp.id=bnp.brand_profile_id
             WHERE bnp.id=subject_uuid AND pc.id=item_row.portfolio_content_id
               AND bp.brand_id=item_row.brand_id AND bnp.active
        ) INTO valid_subject;
      WHEN 'concept_approval' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.concept_candidates cc
             WHERE cc.id=subject_uuid AND cc.accepted_content_id=item_row.portfolio_content_id
               AND cc.status='accepted'
        ) INTO valid_subject;
      WHEN 'script_approval' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.script_versions sv
            JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
             WHERE sv.id=subject_uuid AND sd.portfolio_content_id=item_row.portfolio_content_id
               AND sv.basis_content_version=item_row.content_version AND sv.status='approved'
        ) INTO valid_subject;
      WHEN 'script_revision' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.script_versions sv
            JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
             WHERE sv.id=subject_uuid AND sd.portfolio_content_id=item_row.portfolio_content_id
               AND sv.version>1 AND sv.parent_version_id IS NOT NULL
               AND nullif(btrim(sv.revision_reason),'') IS NOT NULL
        ) INTO valid_subject;
      WHEN 'narration_approval' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.audio_mix_versions amv
            JOIN football_brief.audio_productions ap ON ap.id=amv.audio_production_id
             WHERE amv.id=subject_uuid AND ap.portfolio_content_id=item_row.portfolio_content_id
               AND ap.content_version=item_row.content_version AND ap.status='approved'
               AND amv.status='approved' AND amv.qc_status='pass'
        ) INTO valid_subject;
      WHEN 'narration_revision' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.audio_mix_versions amv
            JOIN football_brief.audio_productions ap ON ap.id=amv.audio_production_id
             WHERE amv.id=subject_uuid AND ap.portfolio_content_id=item_row.portfolio_content_id
               AND amv.version>1 AND amv.parent_mix_version_id IS NOT NULL
        ) INTO valid_subject;
      WHEN 'visual_approval' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.visual_projects vp
             WHERE vp.id=subject_uuid AND vp.portfolio_content_id=item_row.portfolio_content_id
               AND vp.content_version=item_row.content_version AND vp.status='approved'
        ) INTO valid_subject;
      WHEN 'visual_revision' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.visual_shot_versions vsv
            JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
            JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
             WHERE vsv.id=subject_uuid AND vp.portfolio_content_id=item_row.portfolio_content_id
               AND vsv.version>1 AND vsv.parent_version_id IS NOT NULL
               AND nullif(btrim(vsv.revision_reason),'') IS NOT NULL
        ) INTO valid_subject;
      WHEN 'spend_approval' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.production_spend_decisions psd
            JOIN football_brief.shot_routing_plans srp ON srp.id=psd.routing_plan_id
             WHERE psd.id=subject_uuid AND srp.portfolio_content_id=item_row.portfolio_content_id
               AND srp.content_version=item_row.content_version AND srp.status='approved'
               AND psd.decision='approved'
        ) INTO valid_subject;
      WHEN 'artifact_lineage' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.final_releases fr
            JOIN football_brief.shared_artifact_versions sav ON sav.id=fr.output_artifact_version_id
             WHERE sav.id=subject_uuid AND fr.portfolio_content_id=item_row.portfolio_content_id
               AND fr.content_version=item_row.content_version AND fr.status='approved'
               AND sav.status IN ('current','retained')
        ) INTO valid_subject;
      WHEN 'final_qa' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.final_release_qa_reports frq
            JOIN football_brief.final_releases fr ON fr.id=frq.release_id
             WHERE frq.id=subject_uuid AND fr.portfolio_content_id=item_row.portfolio_content_id
               AND fr.content_version=item_row.content_version AND frq.outcome='pass'
        ) INTO valid_subject;
      WHEN 'release_manifest' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.final_releases fr
             WHERE fr.id=subject_uuid AND fr.portfolio_content_id=item_row.portfolio_content_id
               AND fr.content_version=item_row.content_version AND fr.status='approved'
               AND fr.release_manifest IS NOT NULL AND fr.manifest_hash IS NOT NULL
        ) INTO valid_subject;
      WHEN 'publisher_decision','staging_delivery' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.platform_delivery_requests pdr
            JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
            JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
             WHERE pdr.id=subject_uuid AND fr.portfolio_content_id=item_row.portfolio_content_id
               AND fr.content_version=item_row.content_version AND pdr.status='succeeded'
               AND pdt.environment='staging' AND pdt.simulated
        ) INTO valid_subject;
      WHEN 'analytics_observation' THEN
        SELECT EXISTS(
            SELECT 1 FROM football_brief.performance_delivery_observations pdo
             WHERE pdo.id=subject_uuid AND pdo.portfolio_content_id=item_row.portfolio_content_id
               AND pdo.content_version=item_row.content_version
        ) INTO valid_subject;
      ELSE
        valid_subject:=true;
    END CASE;
    IF NOT valid_subject THEN
        RAISE EXCEPTION 'Passed acceptance evidence subject does not match the exact pilot item lineage';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_content_subject_valid
BEFORE INSERT ON football_brief.acceptance_pilot_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_content_subject();

COMMIT;
