-- Fail-closed renderer versioning, activation, preflight, and simulated job binding rules.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_renderer_catalogue_entry()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.renderer_catalogue_entries%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Renderer catalogue entries cannot be deleted';
    END IF;

    IF TG_OP='INSERT' THEN
        IF NEW.version > 1 THEN
            SELECT * INTO parent_row
              FROM football_brief.renderer_catalogue_entries
             WHERE id=NEW.parent_entry_id;
            IF parent_row.id IS NULL
               OR parent_row.provider_key IS DISTINCT FROM NEW.provider_key
               OR parent_row.model_key IS DISTINCT FROM NEW.model_key
               OR parent_row.operation IS DISTINCT FROM NEW.operation
               OR parent_row.version + 1 <> NEW.version
               OR parent_row.status NOT IN ('active','retired') THEN
                RAISE EXCEPTION 'Renderer revisions require the immediate active or retired parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('active','retired') THEN
        IF OLD.status='active'
           AND NEW.status='retired'
           AND NEW.retired_at IS NOT NULL
           AND NEW.retired_by IS NOT NULL
           AND NEW.health_status IS NOT DISTINCT FROM OLD.health_status
           AND NEW.provider_key IS NOT DISTINCT FROM OLD.provider_key
           AND NEW.provider_display_name IS NOT DISTINCT FROM OLD.provider_display_name
           AND NEW.model_key IS NOT DISTINCT FROM OLD.model_key
           AND NEW.model_display_name IS NOT DISTINCT FROM OLD.model_display_name
           AND NEW.operation IS NOT DISTINCT FROM OLD.operation
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_entry_id IS NOT DISTINCT FROM OLD.parent_entry_id
           AND NEW.adapter_kind IS NOT DISTINCT FROM OLD.adapter_kind
           AND NEW.supported_formats IS NOT DISTINCT FROM OLD.supported_formats
           AND NEW.min_duration_seconds IS NOT DISTINCT FROM OLD.min_duration_seconds
           AND NEW.max_duration_seconds IS NOT DISTINCT FROM OLD.max_duration_seconds
           AND NEW.duration_step_seconds IS NOT DISTINCT FROM OLD.duration_step_seconds
           AND NEW.supported_resolutions IS NOT DISTINCT FROM OLD.supported_resolutions
           AND NEW.capabilities IS NOT DISTINCT FROM OLD.capabilities
           AND NEW.expected_latency_seconds IS NOT DISTINCT FROM OLD.expected_latency_seconds
           AND NEW.pricing IS NOT DISTINCT FROM OLD.pricing
           AND NEW.pricing_currency IS NOT DISTINCT FROM OLD.pricing_currency
           AND NEW.quality_rating IS NOT DISTINCT FROM OLD.quality_rating
           AND NEW.commercial_use_allowed IS NOT DISTINCT FROM OLD.commercial_use_allowed
           AND NEW.usage_terms_url IS NOT DISTINCT FROM OLD.usage_terms_url
           AND NEW.usage_evidence_digest IS NOT DISTINCT FROM OLD.usage_evidence_digest
           AND NEW.usage_evidence_recorded_at IS NOT DISTINCT FROM OLD.usage_evidence_recorded_at
           AND NEW.data_handling IS NOT DISTINCT FROM OLD.data_handling
           AND NEW.notes IS NOT DISTINCT FROM OLD.notes
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.activated_by IS NOT DISTINCT FROM OLD.activated_by
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
           AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
            RETURN NEW;
        END IF;

        IF NEW.status IS NOT DISTINCT FROM OLD.status
           AND NEW.health_status IS DISTINCT FROM OLD.health_status
           AND NEW.provider_key IS NOT DISTINCT FROM OLD.provider_key
           AND NEW.provider_display_name IS NOT DISTINCT FROM OLD.provider_display_name
           AND NEW.model_key IS NOT DISTINCT FROM OLD.model_key
           AND NEW.model_display_name IS NOT DISTINCT FROM OLD.model_display_name
           AND NEW.operation IS NOT DISTINCT FROM OLD.operation
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_entry_id IS NOT DISTINCT FROM OLD.parent_entry_id
           AND NEW.adapter_kind IS NOT DISTINCT FROM OLD.adapter_kind
           AND NEW.supported_formats IS NOT DISTINCT FROM OLD.supported_formats
           AND NEW.min_duration_seconds IS NOT DISTINCT FROM OLD.min_duration_seconds
           AND NEW.max_duration_seconds IS NOT DISTINCT FROM OLD.max_duration_seconds
           AND NEW.duration_step_seconds IS NOT DISTINCT FROM OLD.duration_step_seconds
           AND NEW.supported_resolutions IS NOT DISTINCT FROM OLD.supported_resolutions
           AND NEW.capabilities IS NOT DISTINCT FROM OLD.capabilities
           AND NEW.expected_latency_seconds IS NOT DISTINCT FROM OLD.expected_latency_seconds
           AND NEW.pricing IS NOT DISTINCT FROM OLD.pricing
           AND NEW.pricing_currency IS NOT DISTINCT FROM OLD.pricing_currency
           AND NEW.quality_rating IS NOT DISTINCT FROM OLD.quality_rating
           AND NEW.commercial_use_allowed IS NOT DISTINCT FROM OLD.commercial_use_allowed
           AND NEW.usage_terms_url IS NOT DISTINCT FROM OLD.usage_terms_url
           AND NEW.usage_evidence_digest IS NOT DISTINCT FROM OLD.usage_evidence_digest
           AND NEW.usage_evidence_recorded_at IS NOT DISTINCT FROM OLD.usage_evidence_recorded_at
           AND NEW.data_handling IS NOT DISTINCT FROM OLD.data_handling
           AND NEW.notes IS NOT DISTINCT FROM OLD.notes
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.activated_by IS NOT DISTINCT FROM OLD.activated_by
           AND NEW.retired_by IS NOT DISTINCT FROM OLD.retired_by
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
           AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at
           AND NEW.retired_at IS NOT DISTINCT FROM OLD.retired_at THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Active and retired renderer specifications are immutable';
    END IF;

    IF NEW.provider_key IS DISTINCT FROM OLD.provider_key
       OR NEW.model_key IS DISTINCT FROM OLD.model_key
       OR NEW.operation IS DISTINCT FROM OLD.operation
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_entry_id IS DISTINCT FROM OLD.parent_entry_id
       OR NEW.adapter_kind IS DISTINCT FROM OLD.adapter_kind
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Renderer catalogue identity is immutable';
    END IF;

    IF OLD.status='draft' AND NEW.status='active' THEN
        IF cardinality(NEW.supported_formats)=0
           OR jsonb_array_length(NEW.supported_resolutions)=0
           OR NEW.health_status NOT IN ('healthy','degraded')
           OR NEW.commercial_use_allowed=false
           OR NEW.activated_at IS NULL
           OR NEW.activated_by IS NULL THEN
            RAISE EXCEPTION 'Renderer activation requires formats, resolutions, usable health, commercial rights, and activation evidence';
        END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid renderer catalogue status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER renderer_catalogue_entry_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.renderer_catalogue_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_renderer_catalogue_entry();

CREATE OR REPLACE FUNCTION football_brief.apply_renderer_health_observation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE football_brief.renderer_catalogue_entries
       SET health_status=NEW.status
     WHERE id=NEW.renderer_catalogue_entry_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER renderer_health_observation_apply
AFTER INSERT ON football_brief.renderer_health_observations
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_renderer_health_observation();

CREATE OR REPLACE FUNCTION football_brief.reject_renderer_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Renderer health, preflight, and job binding evidence is append-only';
END;
$$;

CREATE TRIGGER renderer_health_immutable
BEFORE UPDATE OR DELETE ON football_brief.renderer_health_observations
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_renderer_evidence_mutation();

CREATE TRIGGER renderer_preflight_immutable
BEFORE UPDATE OR DELETE ON football_brief.renderer_preflight_records
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_renderer_evidence_mutation();

CREATE TRIGGER renderer_job_binding_immutable
BEFORE UPDATE OR DELETE ON football_brief.renderer_job_bindings
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_renderer_evidence_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_renderer_job_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    job_row football_brief.generation_jobs%ROWTYPE;
    preflight_row football_brief.renderer_preflight_records%ROWTYPE;
    entry_row football_brief.renderer_catalogue_entries%ROWTYPE;
BEGIN
    SELECT * INTO job_row FROM football_brief.generation_jobs WHERE id=NEW.generation_job_id;
    SELECT * INTO preflight_row FROM football_brief.renderer_preflight_records WHERE id=NEW.renderer_preflight_id;
    SELECT * INTO entry_row FROM football_brief.renderer_catalogue_entries WHERE id=NEW.renderer_catalogue_entry_id;

    IF job_row.id IS NULL OR preflight_row.id IS NULL OR entry_row.id IS NULL THEN
        RAISE EXCEPTION 'Renderer job binding references missing evidence';
    END IF;
    IF preflight_row.accepted=false
       OR preflight_row.renderer_catalogue_entry_id IS DISTINCT FROM entry_row.id
       OR preflight_row.request_fingerprint IS DISTINCT FROM NEW.request_fingerprint THEN
        RAISE EXCEPTION 'Renderer job binding requires the exact accepted preflight';
    END IF;
    IF job_row.portfolio_content_id IS DISTINCT FROM preflight_row.portfolio_content_id
       OR job_row.content_version IS DISTINCT FROM preflight_row.content_version
       OR job_row.job_type <> 'premium_clip'
       OR job_row.provider IS DISTINCT FROM entry_row.provider_key
       OR job_row.model_id IS DISTINCT FROM entry_row.model_key THEN
        RAISE EXCEPTION 'Renderer job does not match the accepted catalogue request';
    END IF;
    IF entry_row.adapter_kind <> 'simulated'
       OR entry_row.provider_key <> 'simulated'
       OR job_row.estimated_cost_usd <> 0
       OR job_row.reserved_cost_usd <> 0 THEN
        RAISE EXCEPTION 'P93 permits only zero-fee simulated renderer jobs';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER renderer_job_binding_valid
BEFORE INSERT ON football_brief.renderer_job_bindings
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_renderer_job_binding();

COMMIT;
