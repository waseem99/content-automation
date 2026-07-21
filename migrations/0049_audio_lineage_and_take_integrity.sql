-- Fail-closed approved-script, pinned-preset, local take, pronunciation, asset, and rights integrity.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_audio_production()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    valid_lineage_count integer;
    next_mix_version integer;
    next_mix_parent uuid;
    next_mix_status text;
    old_mix_version integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audio productions cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        SELECT count(*) INTO valid_lineage_count
          FROM football_brief.script_versions sv
          JOIN football_brief.script_documents sd ON sd.id = sv.script_document_id
          JOIN football_brief.portfolio_content pc ON pc.id = sd.portfolio_content_id
          JOIN football_brief.brand_profiles bp ON bp.id = NEW.brand_profile_id
          JOIN football_brief.brand_narration_presets bnp ON bnp.id = NEW.narration_preset_id
          JOIN football_brief.approved_voices av ON av.id = NEW.approved_voice_id
         WHERE sv.id = NEW.script_version_id
           AND sv.status = 'approved'
           AND sd.current_version_id = sv.id
           AND sd.portfolio_content_id = NEW.portfolio_content_id
           AND sv.basis_content_version = NEW.content_version
           AND pc.version = NEW.content_version
           AND pc.brand_profile_id = NEW.brand_profile_id
           AND pc.narration_preset_id = NEW.narration_preset_id
           AND bp.id = bnp.brand_profile_id
           AND bp.status IN ('active', 'retired')
           AND bnp.active = true
           AND bnp.approved_voice_id = av.id
           AND av.approval_status = 'approved'
           AND (av.expires_at IS NULL OR av.expires_at > now())
           AND NEW.provider = av.provider
           AND NEW.provider_voice_id = av.provider_voice_id
           AND lower(NEW.provider) IN ('kokoro', 'kokoro-onnx')
           AND EXISTS (
               SELECT 1 FROM unnest(av.allowed_languages) language_code
                WHERE lower(language_code) IN (
                    lower(sv.language), lower(split_part(sv.language, '-', 1))
                )
           )
           AND (
               cardinality(av.allowed_platforms) = 0
               OR EXISTS (
                   SELECT 1 FROM unnest(av.allowed_platforms) platform_code
                    WHERE lower(platform_code) = lower(sv.platform)
               )
           );

        IF valid_lineage_count <> 1 THEN
            RAISE EXCEPTION 'Audio production requires the current approved script, pinned preset, and eligible Kokoro voice';
        END IF;
        IF nullif(btrim(NEW.model_id), '') IS NULL
           OR jsonb_typeof(NEW.preset_snapshot) IS DISTINCT FROM 'object'
           OR NEW.preset_snapshot = '{}'::jsonb
           OR jsonb_typeof(NEW.pronunciation_snapshot) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'Audio production requires model, preset, and pronunciation lineage snapshots';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.script_version_id IS DISTINCT FROM OLD.script_version_id
       OR NEW.brand_profile_id IS DISTINCT FROM OLD.brand_profile_id
       OR NEW.narration_preset_id IS DISTINCT FROM OLD.narration_preset_id
       OR NEW.approved_voice_id IS DISTINCT FROM OLD.approved_voice_id
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.provider_voice_id IS DISTINCT FROM OLD.provider_voice_id
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.preset_snapshot IS DISTINCT FROM OLD.preset_snapshot
       OR NEW.pronunciation_snapshot IS DISTINCT FROM OLD.pronunciation_snapshot
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Audio production identity and provider lineage are immutable';
    END IF;
    IF NEW.lock_version <> OLD.lock_version + 1 THEN
        RAISE EXCEPTION 'Audio production updates must increment lock_version by exactly one';
    END IF;

    IF NEW.current_mix_version_id IS DISTINCT FROM OLD.current_mix_version_id THEN
        SELECT amv.version, amv.parent_mix_version_id, amv.status
          INTO next_mix_version, next_mix_parent, next_mix_status
          FROM football_brief.audio_mix_versions amv
         WHERE amv.id = NEW.current_mix_version_id
           AND amv.audio_production_id = NEW.id;
        IF next_mix_status IS DISTINCT FROM 'working' THEN
            RAISE EXCEPTION 'Audio production can point only to its working mix version';
        END IF;
        IF OLD.current_mix_version_id IS NULL THEN
            IF next_mix_version <> 1 OR next_mix_parent IS NOT NULL OR OLD.status <> 'working' OR NEW.status <> 'working' THEN
                RAISE EXCEPTION 'Initial audio mix pointer must select version one';
            END IF;
        ELSE
            SELECT amv.version INTO old_mix_version
              FROM football_brief.audio_mix_versions amv
             WHERE amv.id = OLD.current_mix_version_id;
            IF OLD.status NOT IN ('changes_requested', 'rejected')
               OR NEW.status <> 'working'
               OR next_mix_parent IS DISTINCT FROM OLD.current_mix_version_id
               OR next_mix_version <> old_mix_version + 1 THEN
                RAISE EXCEPTION 'Audio mix revisions must be immediate children of a reviewed mix';
            END IF;
        END IF;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'working' AND NEW.status IN ('in_review', 'superseded') THEN
            NULL;
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
            NULL;
        ELSIF OLD.status IN ('changes_requested', 'rejected') AND NEW.status = 'working' THEN
            NULL;
        ELSIF OLD.status = 'approved' AND NEW.status = 'superseded' THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid audio production status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF NEW.status IN ('in_review', 'approved', 'changes_requested', 'rejected') THEN
        IF NEW.current_mix_version_id IS NULL THEN
            RAISE EXCEPTION 'Reviewed audio production requires a current mix version';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM football_brief.audio_mix_versions amv
             WHERE amv.id = NEW.current_mix_version_id
               AND amv.audio_production_id = NEW.id
               AND amv.status = NEW.status
        ) THEN
            RAISE EXCEPTION 'Audio production status must match its current mix version';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_production_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_productions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_production();

CREATE OR REPLACE FUNCTION football_brief.protect_audio_paragraph()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    required_script_version uuid;
    section_script_version uuid;
    production_status text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audio paragraphs cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Audio paragraphs are immutable script evidence';
    END IF;

    SELECT ap.script_version_id, ap.status
      INTO required_script_version, production_status
      FROM football_brief.audio_productions ap
     WHERE ap.id = NEW.audio_production_id;
    SELECT ss.script_version_id INTO section_script_version
      FROM football_brief.script_sections ss
     WHERE ss.id = NEW.script_section_id;

    IF production_status IS DISTINCT FROM 'working'
       OR section_script_version IS DISTINCT FROM required_script_version THEN
        RAISE EXCEPTION 'Audio paragraphs must come from the exact approved script while production is working';
    END IF;
    IF NEW.text_fingerprint !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Audio paragraph text fingerprint is invalid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_paragraph_immutable
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_paragraphs
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_audio_paragraph();

CREATE OR REPLACE FUNCTION football_brief.validate_audio_pronunciation_override()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    production_status text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Pronunciation overrides cannot be deleted';
    END IF;
    SELECT ap.status INTO production_status
      FROM football_brief.audio_productions ap
     WHERE ap.id = COALESCE(NEW.audio_production_id, OLD.audio_production_id);
    IF production_status NOT IN ('working', 'changes_requested') THEN
        RAISE EXCEPTION 'Pronunciation overrides can change only before audio submission';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF NEW.audio_production_id IS DISTINCT FROM OLD.audio_production_id
           OR NEW.token IS DISTINCT FROM OLD.token
           OR NEW.pronunciation IS DISTINCT FROM OLD.pronunciation
           OR NEW.locale IS DISTINCT FROM OLD.locale
           OR NEW.reason IS DISTINCT FROM OLD.reason
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR OLD.active = false
           OR NEW.active <> false THEN
            RAISE EXCEPTION 'Pronunciation overrides are immutable except one-time deactivation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_pronunciation_override_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_pronunciation_overrides
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_pronunciation_override();

CREATE OR REPLACE FUNCTION football_brief.validate_audio_segment_take()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    production_row football_brief.audio_productions%ROWTYPE;
    paragraph_production uuid;
    job_valid_count integer;
    asset_valid_count integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audio segment takes cannot be deleted';
    END IF;

    SELECT * INTO production_row
      FROM football_brief.audio_productions ap
     WHERE ap.id = COALESCE(NEW.audio_production_id, OLD.audio_production_id);

    IF TG_OP = 'INSERT' THEN
        SELECT apar.audio_production_id INTO paragraph_production
          FROM football_brief.audio_paragraphs apar
         WHERE apar.id = NEW.paragraph_id;
        IF paragraph_production IS DISTINCT FROM NEW.audio_production_id
           OR production_row.status NOT IN ('working', 'changes_requested') THEN
            RAISE EXCEPTION 'Audio take paragraph must belong to a writable production';
        END IF;
        IF NEW.provider IS DISTINCT FROM production_row.provider
           OR NEW.model_id IS DISTINCT FROM production_row.model_id
           OR NEW.approved_voice_id IS DISTINCT FROM production_row.approved_voice_id
           OR NEW.narration_preset_id IS DISTINCT FROM production_row.narration_preset_id
           OR NEW.external_fee_incurred = true
           OR NEW.actual_cost_usd <> 0 THEN
            RAISE EXCEPTION 'P90 audio takes must use the pinned local Kokoro lineage without an external fee';
        END IF;
        IF NEW.generation_job_id IS NOT NULL THEN
            SELECT count(*) INTO job_valid_count
              FROM football_brief.generation_jobs gj
             WHERE gj.id = NEW.generation_job_id
               AND gj.portfolio_content_id = production_row.portfolio_content_id
               AND gj.content_version = production_row.content_version
               AND gj.job_type = 'narration'
               AND gj.provider = production_row.provider
               AND gj.model_id = production_row.model_id
               AND gj.input_payload ->> 'script_version_id' = production_row.script_version_id::text
               AND gj.input_payload ->> 'audio_production_id' = NEW.audio_production_id::text
               AND gj.input_payload ->> 'paragraph_id' = NEW.paragraph_id::text;
            IF job_valid_count <> 1 THEN
                RAISE EXCEPTION 'Audio take generation job lineage is invalid';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.audio_production_id IS DISTINCT FROM OLD.audio_production_id
       OR NEW.paragraph_id IS DISTINCT FROM OLD.paragraph_id
       OR NEW.take_version IS DISTINCT FROM OLD.take_version
       OR NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.approved_voice_id IS DISTINCT FROM OLD.approved_voice_id
       OR NEW.narration_preset_id IS DISTINCT FROM OLD.narration_preset_id
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.pronunciation_snapshot IS DISTINCT FROM OLD.pronunciation_snapshot
       OR NEW.actual_cost_usd IS DISTINCT FROM OLD.actual_cost_usd
       OR NEW.external_fee_incurred IS DISTINCT FROM OLD.external_fee_incurred
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Audio take identity and local provider lineage are immutable';
    END IF;
    IF OLD.status IN ('selected', 'failed', 'superseded') THEN
        RAISE EXCEPTION 'Terminal audio takes are immutable';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'queued' AND NEW.status IN ('generated', 'failed') THEN
            NULL;
        ELSIF OLD.status = 'generated' AND NEW.status IN ('selected', 'failed', 'superseded') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid audio take status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF NEW.status IN ('generated', 'selected') THEN
        SELECT count(*) INTO asset_valid_count
          FROM football_brief.assets a
         WHERE a.id = NEW.asset_id
           AND a.asset_type = 'audio'
           AND a.lifecycle_status = 'approved';
        IF asset_valid_count <> 1
           OR NEW.duration_seconds IS NULL
           OR NEW.sample_rate_hz IS NULL
           OR NEW.channels IS NULL
           OR NEW.qc_status = 'pending' THEN
            RAISE EXCEPTION 'Generated audio takes require an approved audio asset and complete QC metadata';
        END IF;
    END IF;
    IF NEW.status = 'selected' AND NEW.qc_status <> 'pass' THEN
        RAISE EXCEPTION 'Only a QC-passing audio take can be selected';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_segment_take_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_segment_takes
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_segment_take();

CREATE OR REPLACE FUNCTION football_brief.validate_audio_mix_track()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    mix_status text;
    content_platform text;
    asset_valid_count integer;
    rights_valid_count integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        SELECT amv.status INTO mix_status
          FROM football_brief.audio_mix_versions amv
         WHERE amv.id = OLD.audio_mix_version_id;
        IF mix_status <> 'working' THEN
            RAISE EXCEPTION 'Submitted audio mix tracks are immutable';
        END IF;
        RETURN OLD;
    END IF;

    SELECT amv.status, b.primary_platform
      INTO mix_status, content_platform
      FROM football_brief.audio_mix_versions amv
      JOIN football_brief.audio_productions ap ON ap.id = amv.audio_production_id
      JOIN football_brief.portfolio_content pc ON pc.id = ap.portfolio_content_id
      JOIN football_brief.monthly_content_plans mp ON mp.id = pc.plan_id
      JOIN football_brief.brands b ON b.id = mp.brand_id
     WHERE amv.id = NEW.audio_mix_version_id;
    IF mix_status <> 'working' THEN
        RAISE EXCEPTION 'Audio mix tracks can change only while the mix is working';
    END IF;

    SELECT count(*) INTO asset_valid_count
      FROM football_brief.assets a
     WHERE a.id = NEW.asset_id
       AND a.asset_type = 'audio'
       AND a.lifecycle_status = 'approved';
    IF asset_valid_count <> 1 THEN
        RAISE EXCEPTION 'Audio mix tracks require an approved canonical audio asset';
    END IF;

    IF NEW.track_role IN ('music', 'sfx') THEN
        SELECT count(*) INTO rights_valid_count
          FROM football_brief.asset_rights ar
         WHERE ar.id = NEW.asset_rights_id
           AND ar.asset_id = NEW.asset_id
           AND ar.approval_status = 'approved'
           AND ar.commercial_use_allowed = true
           AND ar.modification_allowed = true
           AND (ar.expires_at IS NULL OR ar.expires_at > now())
           AND (
               cardinality(ar.platforms) = 0
               OR EXISTS (
                   SELECT 1 FROM unnest(ar.platforms) platform_code
                    WHERE lower(platform_code) = lower(content_platform)
               )
           )
           AND EXISTS (
               SELECT 1 FROM football_brief.rights_evidence re
                WHERE re.asset_id = ar.asset_id
           );
        IF rights_valid_count <> 1 THEN
            RAISE EXCEPTION 'Music and sound effects require approved, evidenced, modifiable commercial rights';
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.audio_mix_version_id IS DISTINCT FROM OLD.audio_mix_version_id
           OR NEW.track_role IS DISTINCT FROM OLD.track_role
           OR NEW.asset_id IS DISTINCT FROM OLD.asset_id
           OR NEW.asset_rights_id IS DISTINCT FROM OLD.asset_rights_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Audio mix track asset and rights identity are immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_mix_track_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_mix_tracks
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_mix_track();

COMMIT;