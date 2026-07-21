-- Immutable renderer capability versions, append-only events, and retained submission evidence.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_production_renderer_catalogue()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Production renderer catalogue entries cannot be deleted';
    END IF;

    IF OLD.status='retired' THEN
        RAISE EXCEPTION 'Retired production renderer entries are immutable';
    END IF;

    IF NEW.renderer_key IS DISTINCT FROM OLD.renderer_key
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_renderer_id IS DISTINCT FROM OLD.parent_renderer_id
       OR NEW.display_name IS DISTINCT FROM OLD.display_name
       OR NEW.adapter_key IS DISTINCT FROM OLD.adapter_key
       OR NEW.operation IS DISTINCT FROM OLD.operation
       OR NEW.output_formats IS DISTINCT FROM OLD.output_formats
       OR NEW.min_duration_seconds IS DISTINCT FROM OLD.min_duration_seconds
       OR NEW.max_duration_seconds IS DISTINCT FROM OLD.max_duration_seconds
       OR NEW.max_width IS DISTINCT FROM OLD.max_width
       OR NEW.max_height IS DISTINCT FROM OLD.max_height
       OR NEW.capabilities IS DISTINCT FROM OLD.capabilities
       OR NEW.expected_seconds_base IS DISTINCT FROM OLD.expected_seconds_base
       OR NEW.expected_seconds_per_second IS DISTINCT FROM OLD.expected_seconds_per_second
       OR NEW.base_cost_usd IS DISTINCT FROM OLD.base_cost_usd
       OR NEW.cost_per_second_usd IS DISTINCT FROM OLD.cost_per_second_usd
       OR NEW.simulated IS DISTINCT FROM OLD.simulated
       OR NEW.configuration IS DISTINCT FROM OLD.configuration
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Production renderer capability and pricing versions are immutable';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status='draft' AND NEW.status IN ('active','retired') THEN
            NULL;
        ELSIF OLD.status='active' AND NEW.status='retired' THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid production renderer status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF NEW.execution_enabled IS DISTINCT FROM OLD.execution_enabled
       AND NOT (NEW.status='retired' AND NEW.execution_enabled=false) THEN
        RAISE EXCEPTION 'Production renderer execution mode is immutable within a catalogue version';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER production_renderer_catalogue_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_renderer_catalogue
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_production_renderer_catalogue();

CREATE OR REPLACE FUNCTION football_brief.protect_production_renderer_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Production renderer events are append-only';
END;
$$;

CREATE TRIGGER production_renderer_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_renderer_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_production_renderer_event();

CREATE OR REPLACE FUNCTION football_brief.protect_production_renderer_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Production renderer attempts cannot be deleted';
    END IF;
    IF OLD.status<>'running' THEN
        RAISE EXCEPTION 'Terminal production renderer attempts are immutable';
    END IF;
    IF NEW.renderer_id IS DISTINCT FROM OLD.renderer_id
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.input_fingerprint IS DISTINCT FROM OLD.input_fingerprint
       OR NEW.request_spec IS DISTINCT FROM OLD.request_spec
       OR NEW.input_payload IS DISTINCT FROM OLD.input_payload
       OR NEW.catalogue_snapshot IS DISTINCT FROM OLD.catalogue_snapshot
       OR NEW.estimated_cost_usd IS DISTINCT FROM OLD.estimated_cost_usd
       OR NEW.expected_seconds IS DISTINCT FROM OLD.expected_seconds
       OR NEW.submitted_by IS DISTINCT FROM OLD.submitted_by
       OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
        RAISE EXCEPTION 'Production renderer attempt inputs and catalogue evidence are immutable';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status NOT IN ('succeeded','failed') THEN
        RAISE EXCEPTION 'Invalid production renderer attempt transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_renderer_attempts_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_renderer_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_production_renderer_attempt();

COMMIT;
