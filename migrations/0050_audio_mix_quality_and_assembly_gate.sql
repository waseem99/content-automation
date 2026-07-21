-- Final mix quality, forced-alignment approval, exact decisions, segment replacement, and assembly gating.

BEGIN;

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

    IF OLD.status IN ('failed', 'superseded') THEN
        RAISE EXCEPTION 'Terminal audio takes are immutable';
    END IF;
    IF OLD.status = 'selected' THEN
        IF NEW.status <> 'superseded'
           OR NEW.asset_id IS DISTINCT FROM OLD.asset_id
           OR NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds
           OR NEW.sample_rate_hz IS DISTINCT FROM OLD.sample_rate_hz
           OR NEW.channels IS DISTINCT FROM OLD.channels
           OR NEW.integrated_lufs IS DISTINCT FROM OLD.integrated_lufs
           OR NEW.true_peak_dbfs IS DISTINCT FROM OLD.true_peak_dbfs
           OR NEW.clipping_count IS DISTINCT FROM OLD.clipping_count
           OR NEW.silence_ratio IS DISTINCT FROM OLD.silence_ratio
           OR NEW.qc_status IS DISTINCT FROM OLD.qc_status
           OR NEW.qc_evidence IS DISTINCT FROM OLD.qc_evidence
           OR NEW.timing_source IS DISTINCT FROM OLD.timing_source
           OR NEW.word_timings IS DISTINCT FROM OLD.word_timings THEN
            RAISE EXCEPTION 'Selected audio takes are immutable except supersession';
        END IF;
        RETURN NEW;
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
           OR NEW.qc_status = 'pending'
           OR jsonb_typeof(NEW.qc_evidence) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'Generated audio takes require an approved audio asset and complete QC metadata';
        END IF;
        IF NEW.timing_source <> 'none'
           AND (jsonb_typeof(NEW.word_timings) IS DISTINCT FROM 'array'
                OR jsonb_array_length(NEW.word_timings) = 0) THEN
            RAISE EXCEPTION 'Recorded audio timing requires word timing evidence';
        END IF;
    END IF;
    IF NEW.status = 'selected' AND NEW.qc_status <> 'pass' THEN
        RAISE EXCEPTION 'Only a QC-passing audio take can be selected';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION football_brief.validate_audio_mix_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    production_status text;
    production_current_mix uuid;
    parent_version integer;
    parent_status text;
    paragraph_total integer;
    selected_total integer;
    invalid_take_total integer;
    narration_track_total integer;
    approved_asset_total integer;
    target_duration numeric(12,3);
    duration_tolerance numeric(8,3);
    allowed_duration_delta numeric(12,3);
    unresolved_action_total integer;
    matching_decision_total integer;
    proportional_take_total integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audio mix versions cannot be deleted';
    END IF;

    SELECT ap.status, ap.current_mix_version_id
      INTO production_status, production_current_mix
      FROM football_brief.audio_productions ap
     WHERE ap.id = NEW.audio_production_id;

    IF TG_OP = 'INSERT' THEN
        IF NEW.version = 1 THEN
            IF NEW.parent_mix_version_id IS NOT NULL OR production_status <> 'working' OR production_current_mix IS NOT NULL THEN
                RAISE EXCEPTION 'Initial audio mix must be version one without a parent';
            END IF;
        ELSE
            SELECT amv.version, amv.status INTO parent_version, parent_status
              FROM football_brief.audio_mix_versions amv
             WHERE amv.id = NEW.parent_mix_version_id
               AND amv.audio_production_id = NEW.audio_production_id;
            IF parent_version IS NULL
               OR NEW.version <> parent_version + 1
               OR parent_status NOT IN ('changes_requested', 'rejected')
               OR production_status NOT IN ('changes_requested', 'rejected') THEN
                RAISE EXCEPTION 'Audio mix revisions require an immediate reviewed parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.audio_production_id IS DISTINCT FROM OLD.audio_production_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_mix_version_id IS DISTINCT FROM OLD.parent_mix_version_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Audio mix version identity is immutable';
    END IF;
    IF OLD.status IN ('approved', 'changes_requested', 'rejected', 'superseded') THEN
        RAISE EXCEPTION 'Terminal audio mix versions are immutable';
    END IF;
    IF OLD.status = 'in_review' THEN
        IF NEW.narration_asset_id IS DISTINCT FROM OLD.narration_asset_id
           OR NEW.final_mix_asset_id IS DISTINCT FROM OLD.final_mix_asset_id
           OR NEW.target_lufs IS DISTINCT FROM OLD.target_lufs
           OR NEW.peak_limit_dbfs IS DISTINCT FROM OLD.peak_limit_dbfs
           OR NEW.measured_lufs IS DISTINCT FROM OLD.measured_lufs
           OR NEW.true_peak_dbfs IS DISTINCT FROM OLD.true_peak_dbfs
           OR NEW.clipping_count IS DISTINCT FROM OLD.clipping_count
           OR NEW.silence_ratio IS DISTINCT FROM OLD.silence_ratio
           OR NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds
           OR NEW.qc_status IS DISTINCT FROM OLD.qc_status
           OR NEW.waveform_metadata IS DISTINCT FROM OLD.waveform_metadata
           OR NEW.segment_snapshot IS DISTINCT FROM OLD.segment_snapshot
           OR NEW.mix_settings IS DISTINCT FROM OLD.mix_settings
           OR NEW.alignment_source IS DISTINCT FROM OLD.alignment_source
           OR NEW.last_edited_by IS DISTINCT FROM OLD.last_edited_by
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
            RAISE EXCEPTION 'Submitted audio mix versions are immutable';
        END IF;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'working' AND NEW.status = 'in_review' THEN
            NULL;
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid audio mix status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF OLD.status = 'working' AND NEW.status = 'in_review' THEN
        SELECT count(*) INTO paragraph_total
          FROM football_brief.audio_paragraphs apar
         WHERE apar.audio_production_id = NEW.audio_production_id;
        SELECT count(*) INTO selected_total
          FROM football_brief.audio_segment_takes ast
         WHERE ast.audio_production_id = NEW.audio_production_id
           AND ast.status = 'selected';
        SELECT count(*) INTO invalid_take_total
          FROM football_brief.audio_segment_takes ast
         WHERE ast.audio_production_id = NEW.audio_production_id
           AND ast.status = 'selected'
           AND (
               ast.qc_status <> 'pass'
               OR ast.asset_id IS NULL
               OR ast.clipping_count <> 0
               OR ast.timing_source = 'none'
           );
        SELECT count(*) INTO narration_track_total
          FROM football_brief.audio_mix_tracks amt
         WHERE amt.audio_mix_version_id = NEW.id
           AND amt.track_role = 'narration'
           AND amt.asset_id = NEW.narration_asset_id;
        SELECT count(*) INTO approved_asset_total
          FROM football_brief.assets a
         WHERE a.id IN (NEW.narration_asset_id, NEW.final_mix_asset_id)
           AND a.asset_type = 'audio'
           AND a.lifecycle_status = 'approved';
        SELECT sv.target_duration_seconds, sv.duration_tolerance_percent
          INTO target_duration, duration_tolerance
          FROM football_brief.audio_productions ap
          JOIN football_brief.script_versions sv ON sv.id = ap.script_version_id
         WHERE ap.id = NEW.audio_production_id;
        allowed_duration_delta := target_duration * (duration_tolerance / 100);

        IF paragraph_total = 0 OR selected_total <> paragraph_total OR invalid_take_total <> 0 THEN
            RAISE EXCEPTION 'Every audio paragraph requires one selected QC-passing timed take';
        END IF;
        IF NEW.narration_asset_id IS NULL OR NEW.final_mix_asset_id IS NULL
           OR narration_track_total <> 1 OR approved_asset_total <> 2 THEN
            RAISE EXCEPTION 'Submitted audio requires approved narration and final-mix assets';
        END IF;
        IF NEW.qc_status <> 'pass'
           OR NEW.measured_lufs IS NULL
           OR abs(NEW.measured_lufs - NEW.target_lufs) > 1.0
           OR NEW.true_peak_dbfs IS NULL
           OR NEW.true_peak_dbfs > NEW.peak_limit_dbfs
           OR NEW.clipping_count <> 0
           OR NEW.silence_ratio IS NULL
           OR NEW.silence_ratio > 0.25 THEN
            RAISE EXCEPTION 'Audio mix loudness, peak, clipping, or silence quality limits failed';
        END IF;
        IF NEW.duration_seconds IS NULL
           OR abs(NEW.duration_seconds - target_duration) > allowed_duration_delta THEN
            RAISE EXCEPTION 'Audio mix duration is outside the approved script tolerance';
        END IF;
        IF jsonb_typeof(NEW.waveform_metadata) IS DISTINCT FROM 'object'
           OR NEW.waveform_metadata = '{}'::jsonb
           OR jsonb_typeof(NEW.segment_snapshot) IS DISTINCT FROM 'array'
           OR jsonb_array_length(NEW.segment_snapshot) <> paragraph_total
           OR NEW.alignment_source = 'none' THEN
            RAISE EXCEPTION 'Audio mix requires waveform, segment, and alignment provenance';
        END IF;
    END IF;

    IF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
        SELECT count(*) INTO matching_decision_total
          FROM football_brief.audio_review_decisions ard
         WHERE ard.audio_mix_version_id = NEW.id
           AND ard.audio_production_id = NEW.audio_production_id
           AND ard.decision = NEW.status;
        IF matching_decision_total <> 1 THEN
            RAISE EXCEPTION 'Audio decision must match the exact submitted mix version and status';
        END IF;
    END IF;

    IF OLD.status = 'in_review' AND NEW.status = 'approved' THEN
        SELECT count(*) INTO unresolved_action_total
          FROM football_brief.audio_review_actions ara
         WHERE ara.audio_mix_version_id = NEW.id
           AND ara.resolved_at IS NULL
           AND ara.action_type IN ('pronunciation', 'pace', 'tone', 'paragraph_replacement', 'mix');
        SELECT count(*) INTO proportional_take_total
          FROM football_brief.audio_segment_takes ast
         WHERE ast.audio_production_id = NEW.audio_production_id
           AND ast.status = 'selected'
           AND ast.timing_source <> 'forced_alignment';
        IF unresolved_action_total <> 0 THEN
            RAISE EXCEPTION 'Unresolved audio review actions block approval';
        END IF;
        IF NEW.alignment_source <> 'forced_alignment' OR proportional_take_total <> 0 THEN
            RAISE EXCEPTION 'Final audio approval requires forced alignment for every selected take';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_mix_version_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.audio_mix_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_audio_mix_version();

CREATE OR REPLACE FUNCTION football_brief.apply_audio_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE football_brief.audio_mix_versions
       SET status = NEW.decision,
           decided_at = now()
     WHERE id = NEW.audio_mix_version_id
       AND audio_production_id = NEW.audio_production_id;

    UPDATE football_brief.audio_productions
       SET status = NEW.decision,
           decided_at = now(),
           lock_version = lock_version + 1
     WHERE id = NEW.audio_production_id
       AND current_mix_version_id = NEW.audio_mix_version_id
       AND lock_version = NEW.production_lock_version;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Audio review decision could not advance the current production';
    END IF;

    INSERT INTO football_brief.audio_production_events
        (audio_production_id, audio_mix_version_id, event, actor, details)
    VALUES (
        NEW.audio_production_id,
        NEW.audio_mix_version_id,
        NEW.decision,
        NEW.reviewer_operator_id,
        jsonb_build_object('decision_id', NEW.id, 'rationale', NEW.rationale)
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER audio_review_decision_apply
AFTER INSERT ON football_brief.audio_review_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_audio_review_decision();

CREATE OR REPLACE FUNCTION football_brief.require_approved_audio_for_assembly_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    mix_version_text text;
    requested_mix_id uuid;
    approved_mix_total integer;
BEGIN
    IF NEW.job_type <> 'assembly' THEN
        RETURN NEW;
    END IF;

    mix_version_text := NEW.input_payload ->> 'audio_mix_version_id';
    IF mix_version_text IS NULL
       OR mix_version_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN
        RAISE EXCEPTION 'Assembly jobs require an approved audio_mix_version_id';
    END IF;
    requested_mix_id := mix_version_text::uuid;

    SELECT count(*) INTO approved_mix_total
      FROM football_brief.audio_mix_versions amv
      JOIN football_brief.audio_productions ap ON ap.id = amv.audio_production_id
      JOIN football_brief.assets a ON a.id = amv.final_mix_asset_id
     WHERE amv.id = requested_mix_id
       AND amv.status = 'approved'
       AND amv.alignment_source = 'forced_alignment'
       AND amv.qc_status = 'pass'
       AND ap.current_mix_version_id = amv.id
       AND ap.status = 'approved'
       AND ap.portfolio_content_id = NEW.portfolio_content_id
       AND ap.content_version = NEW.content_version
       AND a.asset_type = 'audio'
       AND a.lifecycle_status = 'approved';

    IF approved_mix_total <> 1 THEN
        RAISE EXCEPTION 'Final assembly requires the current approved QC-passing audio mix';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_audio_assembly_gate
BEFORE INSERT ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.require_approved_audio_for_assembly_job();

COMMIT;