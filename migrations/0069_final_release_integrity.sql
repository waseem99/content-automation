-- Fail-closed exact input approval, assembly, QA, playback, and final release integrity.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.reject_final_release_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Final release evidence is append-only';
END;
$$;

CREATE TRIGGER final_release_input_approvals_immutable
BEFORE UPDATE OR DELETE ON football_brief.final_release_input_approvals
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_final_release_append_only_mutation();
CREATE TRIGGER final_release_qa_reports_immutable
BEFORE UPDATE OR DELETE ON football_brief.final_release_qa_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_final_release_append_only_mutation();
CREATE TRIGGER final_release_playback_reviews_immutable
BEFORE UPDATE OR DELETE ON football_brief.final_release_playback_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_final_release_append_only_mutation();
CREATE TRIGGER final_release_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.final_release_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_final_release_append_only_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_platform_render_profile()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    parent_row football_brief.platform_render_profiles%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Platform render profiles cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.platform_render_profiles WHERE id=NEW.parent_profile_id;
            IF parent_row.id IS NULL OR parent_row.profile_key IS DISTINCT FROM NEW.profile_key
               OR parent_row.version+1<>NEW.version OR parent_row.status<>'retired' THEN
                RAISE EXCEPTION 'Render profile revisions require the immediately retired parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status='retired' THEN RAISE EXCEPTION 'Retired platform render profiles are immutable'; END IF;
    IF NEW.profile_key IS DISTINCT FROM OLD.profile_key
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_profile_id IS DISTINCT FROM OLD.parent_profile_id
       OR NEW.display_name IS DISTINCT FROM OLD.display_name
       OR NEW.platform IS DISTINCT FROM OLD.platform
       OR NEW.width IS DISTINCT FROM OLD.width
       OR NEW.height IS DISTINCT FROM OLD.height
       OR NEW.fps IS DISTINCT FROM OLD.fps
       OR NEW.container IS DISTINCT FROM OLD.container
       OR NEW.video_codec IS DISTINCT FROM OLD.video_codec
       OR NEW.audio_codec IS DISTINCT FROM OLD.audio_codec
       OR NEW.video_bitrate_kbps IS DISTINCT FROM OLD.video_bitrate_kbps
       OR NEW.audio_bitrate_kbps IS DISTINCT FROM OLD.audio_bitrate_kbps
       OR NEW.min_duration_seconds IS DISTINCT FROM OLD.min_duration_seconds
       OR NEW.max_duration_seconds IS DISTINCT FROM OLD.max_duration_seconds
       OR NEW.safe_area IS DISTINCT FROM OLD.safe_area
       OR NEW.captions_required IS DISTINCT FROM OLD.captions_required
       OR NEW.caption_format IS DISTINCT FROM OLD.caption_format
       OR NEW.watermark_policy IS DISTINCT FROM OLD.watermark_policy
       OR NEW.disclosure_required IS DISTINCT FROM OLD.disclosure_required
       OR NEW.target_loudness_lufs IS DISTINCT FROM OLD.target_loudness_lufs
       OR NEW.loudness_tolerance_lu IS DISTINCT FROM OLD.loudness_tolerance_lu
       OR NEW.max_true_peak_dbfs IS DISTINCT FROM OLD.max_true_peak_dbfs
       OR NEW.max_av_sync_offset_ms IS DISTINCT FROM OLD.max_av_sync_offset_ms
       OR NEW.configuration IS DISTINCT FROM OLD.configuration
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Platform render profile contract is immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='active'
       AND NEW.activated_by IS NOT NULL AND NEW.activated_at IS NOT NULL THEN RETURN NEW; END IF;
    IF OLD.status IN ('draft','active') AND NEW.status='retired'
       AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Invalid platform render profile transition';
END;
$$;

CREATE TRIGGER platform_render_profiles_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.platform_render_profiles
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_platform_render_profile();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_input_approval()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    artifact_row football_brief.shared_artifact_versions%ROWTYPE;
BEGIN
    SELECT * INTO artifact_row FROM football_brief.shared_artifact_versions WHERE id=NEW.artifact_version_id;
    IF artifact_row.id IS NULL OR artifact_row.status<>'current' THEN
        RAISE EXCEPTION 'Release input approval requires a current exact artifact version';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_input_approval_valid
BEFORE INSERT ON football_brief.final_release_input_approvals
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_input_approval();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    current_content_version integer;
    profile_row football_brief.platform_render_profiles%ROWTYPE;
    routing_row football_brief.shot_routing_plans%ROWTYPE;
    parent_row football_brief.final_releases%ROWTYPE;
    job_row football_brief.generation_jobs%ROWTYPE;
    output_row football_brief.shared_artifact_versions%ROWTYPE;
    latest_qa football_brief.final_release_qa_reports%ROWTYPE;
    latest_review football_brief.final_release_playback_reviews%ROWTYPE;
    invalid_inputs integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Final releases cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT version INTO current_content_version FROM football_brief.portfolio_content WHERE id=NEW.portfolio_content_id;
        SELECT * INTO profile_row FROM football_brief.platform_render_profiles WHERE id=NEW.render_profile_id;
        IF current_content_version IS DISTINCT FROM NEW.content_version THEN
            RAISE EXCEPTION 'Final release must target the current content version';
        END IF;
        IF profile_row.id IS NULL OR profile_row.status<>'active' THEN
            RAISE EXCEPTION 'Final release requires an active platform render profile';
        END IF;
        IF NEW.routing_plan_id IS NOT NULL THEN
            SELECT * INTO routing_row FROM football_brief.shot_routing_plans WHERE id=NEW.routing_plan_id;
            IF routing_row.id IS NULL OR routing_row.status<>'approved'
               OR routing_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
               OR routing_row.content_version IS DISTINCT FROM NEW.content_version THEN
                RAISE EXCEPTION 'Final release routing plan must be the exact approved content route';
            END IF;
        END IF;
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.final_releases WHERE id=NEW.parent_release_id;
            IF parent_row.id IS NULL OR parent_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
               OR parent_row.content_version IS DISTINCT FROM NEW.content_version
               OR parent_row.version+1<>NEW.version
               OR parent_row.status NOT IN ('approved','changes_requested','rejected','superseded') THEN
                RAISE EXCEPTION 'Release revisions require the immediately decided parent version';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('approved','superseded') THEN
        IF OLD.status='approved' AND NEW.status='superseded'
           AND NEW.superseded_at IS NOT NULL
           AND NEW.lock_version=OLD.lock_version+1
           AND NEW.portfolio_content_id IS NOT DISTINCT FROM OLD.portfolio_content_id
           AND NEW.content_version IS NOT DISTINCT FROM OLD.content_version
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_release_id IS NOT DISTINCT FROM OLD.parent_release_id
           AND NEW.render_profile_id IS NOT DISTINCT FROM OLD.render_profile_id
           AND NEW.routing_plan_id IS NOT DISTINCT FROM OLD.routing_plan_id
           AND NEW.assembly_job_id IS NOT DISTINCT FROM OLD.assembly_job_id
           AND NEW.output_artifact_version_id IS NOT DISTINCT FROM OLD.output_artifact_version_id
           AND NEW.input_hash IS NOT DISTINCT FROM OLD.input_hash
           AND NEW.release_manifest IS NOT DISTINCT FROM OLD.release_manifest
           AND NEW.manifest_hash IS NOT DISTINCT FROM OLD.manifest_hash
           AND NEW.total_cost_usd IS NOT DISTINCT FROM OLD.total_cost_usd
           AND NEW.metadata IS NOT DISTINCT FROM OLD.metadata THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Approved and superseded final releases are immutable';
    END IF;

    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_release_id IS DISTINCT FROM OLD.parent_release_id
       OR NEW.render_profile_id IS DISTINCT FROM OLD.render_profile_id
       OR NEW.routing_plan_id IS DISTINCT FROM OLD.routing_plan_id
       OR NEW.input_hash IS DISTINCT FROM OLD.input_hash
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Final release identity and inputs are immutable';
    END IF;
    IF NEW.lock_version<>OLD.lock_version+1 THEN RAISE EXCEPTION 'Final release lock version conflict'; END IF;

    IF OLD.status='draft' AND NEW.status='assembly_queued' THEN
        SELECT * INTO job_row FROM football_brief.generation_jobs WHERE id=NEW.assembly_job_id;
        IF job_row.id IS NULL OR job_row.job_type<>'assembly'
           OR job_row.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
           OR job_row.content_version IS DISTINCT FROM OLD.content_version
           OR job_row.input_payload->>'final_release_id' IS DISTINCT FROM OLD.id::text
           OR NEW.assembly_queued_at IS NULL THEN
            RAISE EXCEPTION 'Assembly queue transition requires the exact P87 assembly job';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='assembly_queued' AND NEW.status='assembled' THEN
        SELECT * INTO job_row FROM football_brief.generation_jobs WHERE id=OLD.assembly_job_id;
        SELECT * INTO output_row FROM football_brief.shared_artifact_versions WHERE id=NEW.output_artifact_version_id;
        IF job_row.status<>'succeeded' OR output_row.id IS NULL OR output_row.status<>'current'
           OR output_row.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
           OR output_row.content_version IS DISTINCT FROM OLD.content_version
           OR NEW.assembled_at IS NULL THEN
            RAISE EXCEPTION 'Assembly completion requires a succeeded job and current exact output artifact';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='assembled' AND NEW.status='qa_complete' THEN
        SELECT * INTO latest_qa FROM football_brief.final_release_qa_reports
         WHERE release_id=OLD.id ORDER BY created_at DESC,id DESC LIMIT 1;
        IF latest_qa.id IS NULL OR latest_qa.output_artifact_version_id IS DISTINCT FROM OLD.output_artifact_version_id
           OR NEW.qa_completed_at IS NULL THEN
            RAISE EXCEPTION 'QA completion requires an exact output report';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='qa_complete' AND NEW.status='in_review' THEN
        SELECT * INTO latest_qa FROM football_brief.final_release_qa_reports
         WHERE release_id=OLD.id ORDER BY created_at DESC,id DESC LIMIT 1;
        IF latest_qa.outcome<>'pass' OR NEW.submitted_at IS NULL OR NEW.submitted_by IS NULL THEN
            RAISE EXCEPTION 'Final playback review requires passing technical QA';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='in_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN
        SELECT * INTO latest_qa FROM football_brief.final_release_qa_reports
         WHERE release_id=OLD.id ORDER BY created_at DESC,id DESC LIMIT 1;
        SELECT * INTO latest_review FROM football_brief.final_release_playback_reviews
         WHERE release_id=OLD.id ORDER BY created_at DESC,id DESC LIMIT 1;
        IF latest_review.id IS NULL OR latest_review.decision IS DISTINCT FROM NEW.status THEN
            RAISE EXCEPTION 'Release decision must match the latest exact playback review';
        END IF;
        IF NEW.status='approved' THEN
            SELECT count(*) INTO invalid_inputs
              FROM football_brief.final_release_inputs fri
              JOIN football_brief.shared_artifact_versions sav ON sav.id=fri.artifact_version_id
              JOIN football_brief.assets a ON a.id=fri.canonical_asset_id
             WHERE fri.release_id=OLD.id AND fri.required
               AND (sav.status<>'current' OR a.sha256 IS DISTINCT FROM fri.asset_sha256);
            SELECT * INTO output_row FROM football_brief.shared_artifact_versions WHERE id=OLD.output_artifact_version_id;
            IF latest_qa.outcome<>'pass' OR latest_review.decision<>'approved'
               OR invalid_inputs<>0 OR output_row.status<>'current'
               OR NEW.approved_by IS NULL OR NEW.approved_at IS NULL
               OR NEW.release_manifest IS NULL OR NEW.manifest_hash IS NULL THEN
                RAISE EXCEPTION 'Final release approval requires current inputs, passing QA, playback approval, and sealed manifest';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Invalid final release status transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER final_releases_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_input()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    artifact_row football_brief.shared_artifact_versions%ROWTYPE;
    asset_row football_brief.assets%ROWTYPE;
    approval_row football_brief.final_release_input_approvals%ROWTYPE;
    newer_decision integer;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Final release inputs are immutable'; END IF;
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.release_id;
    SELECT * INTO artifact_row FROM football_brief.shared_artifact_versions WHERE id=NEW.artifact_version_id;
    SELECT * INTO asset_row FROM football_brief.assets WHERE id=artifact_row.original_asset_id;
    SELECT * INTO approval_row FROM football_brief.final_release_input_approvals WHERE id=NEW.approval_id;
    SELECT count(*) INTO newer_decision FROM football_brief.final_release_input_approvals
     WHERE artifact_version_id=NEW.artifact_version_id AND role=NEW.role
       AND (created_at,id)>(approval_row.created_at,approval_row.id);
    IF release_row.id IS NULL OR release_row.status<>'draft'
       OR artifact_row.id IS NULL OR artifact_row.status<>'current'
       OR artifact_row.portfolio_content_id IS DISTINCT FROM release_row.portfolio_content_id
       OR artifact_row.content_version IS DISTINCT FROM release_row.content_version
       OR approval_row.id IS NULL OR approval_row.artifact_version_id IS DISTINCT FROM NEW.artifact_version_id
       OR approval_row.role IS DISTINCT FROM NEW.role OR approval_row.decision<>'approved'
       OR newer_decision<>0
       OR NEW.canonical_asset_id IS DISTINCT FROM artifact_row.original_asset_id
       OR NEW.asset_sha256 IS DISTINCT FROM asset_row.sha256 THEN
        RAISE EXCEPTION 'Final release input requires the current exact approved artifact and checksum';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_inputs_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.final_release_inputs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_input();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_qa_report()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    artifact_row football_brief.shared_artifact_versions%ROWTYPE;
    asset_hash char(64);
BEGIN
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.release_id;
    SELECT * INTO artifact_row FROM football_brief.shared_artifact_versions WHERE id=NEW.output_artifact_version_id;
    SELECT sha256 INTO asset_hash FROM football_brief.assets WHERE id=artifact_row.original_asset_id;
    IF release_row.id IS NULL OR release_row.status<>'assembled'
       OR release_row.output_artifact_version_id IS DISTINCT FROM NEW.output_artifact_version_id
       OR release_row.render_profile_id IS DISTINCT FROM NEW.profile_id
       OR release_row.input_hash IS DISTINCT FROM NEW.input_hash
       OR asset_hash IS DISTINCT FROM NEW.output_hash THEN
        RAISE EXCEPTION 'QA report must bind the exact assembled output, profile, inputs, and checksum';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_qa_report_valid
BEFORE INSERT ON football_brief.final_release_qa_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_qa_report();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_playback_review()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    latest_qa football_brief.final_release_qa_reports%ROWTYPE;
BEGIN
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.release_id;
    SELECT * INTO latest_qa FROM football_brief.final_release_qa_reports
     WHERE release_id=NEW.release_id ORDER BY created_at DESC,id DESC LIMIT 1;
    IF release_row.id IS NULL OR release_row.status<>'in_review' OR latest_qa.outcome<>'pass'
       OR NEW.release_lock_version IS DISTINCT FROM release_row.lock_version THEN
        RAISE EXCEPTION 'Playback review requires the exact in-review release with passing QA';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_playback_review_valid
BEFORE INSERT ON football_brief.final_release_playback_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_playback_review();

COMMIT;
