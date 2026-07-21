-- Allow a visual project to be re-reviewed after changes while preserving one decision per exact lock version.

BEGIN;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
      FROM pg_constraint
     WHERE conrelid='football_brief.visual_project_decisions'::regclass
       AND contype='u'
       AND pg_get_constraintdef(oid) ILIKE '%visual_project_id%'
       AND pg_get_constraintdef(oid) NOT ILIKE '%project_lock_version%'
     LIMIT 1;
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE football_brief.visual_project_decisions DROP CONSTRAINT %I',constraint_name);
    END IF;
END;
$$;

ALTER TABLE football_brief.visual_project_decisions
    ADD CONSTRAINT visual_project_decision_lock_unique
    UNIQUE (visual_project_id,project_lock_version);

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
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Visual projects cannot be deleted'; END IF;
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
        IF valid_lineage_count<>1 THEN
            RAISE EXCEPTION 'Visual projects require the current approved script and active matching visual preset';
        END IF;
        IF NEW.provider NOT IN ('comfyui-local','comfyui-sdxl-local')
           OR NEW.external_fee_incurred OR NEW.actual_cost_usd<>0 THEN
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
    IF NEW.lock_version<>OLD.lock_version+1 THEN
        RAISE EXCEPTION 'Visual project updates must increment lock_version by exactly one';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='working' AND NEW.status='ready_for_review' THEN NULL;
        ELSIF OLD.status='ready_for_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN NULL;
        ELSIF OLD.status IN ('changes_requested','rejected') AND NEW.status='working' THEN NULL;
        ELSIF OLD.status='approved' AND NEW.status='superseded' THEN NULL;
        ELSE RAISE EXCEPTION 'Invalid visual project status transition from % to %',OLD.status,NEW.status;
        END IF;
    END IF;
    IF OLD.status='working' AND NEW.status='ready_for_review' THEN
        SELECT count(*),count(*) FILTER (WHERE vs.status='approved')
          INTO shot_total,approved_shot_total
          FROM football_brief.visual_shots vs WHERE vs.visual_project_id=NEW.id;
        IF shot_total=0 OR approved_shot_total<>shot_total THEN
            RAISE EXCEPTION 'Every visual shot must be independently approved before project review';
        END IF;
    END IF;
    IF OLD.status='ready_for_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN
        SELECT count(*) INTO decision_total
          FROM football_brief.visual_project_decisions vpd
         WHERE vpd.visual_project_id=NEW.id
           AND vpd.project_lock_version=OLD.lock_version
           AND vpd.decision=NEW.status;
        IF decision_total<>1 THEN
            RAISE EXCEPTION 'Visual project status requires a matching exact lock-bound decision';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;