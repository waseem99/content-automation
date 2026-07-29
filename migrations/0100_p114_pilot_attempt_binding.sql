-- P114 local clip bindings automatically create the corresponding P113 measured attempt.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.create_p114_pilot_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    job_row football_brief.generation_jobs%ROWTYPE;
    profile_row football_brief.local_video_renderer_profiles%ROWTYPE;
    run_status text;
    next_attempt integer;
    checkpoint_digest text;
BEGIN
    IF NEW.pilot_case_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT * INTO job_row
    FROM football_brief.generation_jobs
    WHERE id=NEW.generation_job_id;

    IF job_row.job_type <> 'local_clip' THEN
        RAISE EXCEPTION 'P114 pilot binding requires a local_clip generation job';
    END IF;

    SELECT * INTO profile_row
    FROM football_brief.local_video_renderer_profiles
    WHERE id=NEW.renderer_profile_id;

    SELECT r.status INTO run_status
    FROM football_brief.video_pilot_cases c
    JOIN football_brief.video_pilot_runs r ON r.id=c.pilot_run_id
    WHERE c.id=NEW.pilot_case_id;

    IF run_status IS DISTINCT FROM 'running' THEN
        RAISE EXCEPTION 'P114 pilot attempt requires a running pilot';
    END IF;

    checkpoint_digest := NEW.model_evidence->'model_files'->0->>'sha256';
    IF checkpoint_digest IS NULL OR checkpoint_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'P114 pilot attempt requires a checkpoint SHA-256';
    END IF;

    SELECT COALESCE(max(attempt_number),0)+1 INTO next_attempt
    FROM football_brief.video_pilot_attempts
    WHERE pilot_case_id=NEW.pilot_case_id;

    INSERT INTO football_brief.video_pilot_attempts
        (pilot_case_id,attempt_number,model_policy_id,renderer_catalogue_entry_id,
         generation_job_id,workflow_key,workflow_sha256,checkpoint_sha256,seed,
         width,height,fps,frame_count,inference_steps,status,started_at,metrics,created_by)
    VALUES
        (NEW.pilot_case_id,next_attempt,profile_row.model_policy_id,
         profile_row.renderer_catalogue_entry_id,NEW.generation_job_id,
         profile_row.workflow_path,NEW.workflow_sha256,checkpoint_digest,
         (job_row.input_payload->>'seed')::bigint,
         (job_row.input_payload->>'width')::integer,
         (job_row.input_payload->>'height')::integer,
         (job_row.input_payload->>'fps')::integer,
         (job_row.input_payload->>'frame_count')::integer,
         (job_row.input_payload->>'inference_steps')::integer,
         'running',now(),
         jsonb_build_object(
             'p114_binding', true,
             'renderer_profile_id', NEW.renderer_profile_id,
             'renderer_profile_version', profile_row.version,
             'distribution_scope', NEW.distribution_scope,
             'release_territories', NEW.release_territories,
             'model_evidence', NEW.model_evidence,
             'external_fee_possible', false,
             'automatic_approval', false
         ),
         NEW.created_by)
    ON CONFLICT (generation_job_id) WHERE generation_job_id IS NOT NULL DO NOTHING;

    UPDATE football_brief.video_pilot_cases
    SET status='running'
    WHERE id=NEW.pilot_case_id AND status IN ('planned','ready');

    RETURN NEW;
END;
$$;

CREATE TRIGGER local_video_clip_create_pilot_attempt
AFTER INSERT ON football_brief.local_video_clip_bindings
FOR EACH ROW EXECUTE FUNCTION football_brief.create_p114_pilot_attempt();

COMMIT;
