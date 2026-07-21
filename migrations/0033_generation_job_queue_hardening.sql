-- Tighten unified generation job workflow bindings and stale-version dead-lettering.

BEGIN;

ALTER TABLE football_brief.generation_jobs
    ADD CONSTRAINT generation_job_workflow_version_fk
    FOREIGN KEY (production_workflow_version_id, production_workflow_id)
    REFERENCES football_brief.production_workflow_versions(id, workflow_id)
    ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION football_brief.protect_generation_job_core()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Generation jobs cannot be deleted';
    END IF;

    IF OLD.status IN ('succeeded', 'cancelled', 'dead_letter') THEN
        RAISE EXCEPTION 'Terminal generation jobs are immutable';
    END IF;

    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.production_workflow_id IS DISTINCT FROM OLD.production_workflow_id
       OR NEW.production_workflow_version_id IS DISTINCT FROM OLD.production_workflow_version_id
       OR NEW.job_type IS DISTINCT FROM OLD.job_type
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_id IS DISTINCT FROM OLD.model_id
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.input_payload IS DISTINCT FROM OLD.input_payload
       OR NEW.timeout_seconds IS DISTINCT FROM OLD.timeout_seconds
       OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.legacy_source IS DISTINCT FROM OLD.legacy_source THEN
        RAISE EXCEPTION 'Generation job identity and inputs are immutable';
    END IF;

    IF NEW.attempt_count < OLD.attempt_count THEN
        RAISE EXCEPTION 'Generation job attempt count cannot decrease';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled', 'dead_letter') THEN
            NULL;
        ELSIF OLD.status = 'running' AND NEW.status IN (
            'queued', 'succeeded', 'failed', 'cancelled', 'dead_letter'
        ) THEN
            NULL;
        ELSIF OLD.status = 'failed' AND NEW.status IN ('queued', 'cancelled', 'dead_letter') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid generation job status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
