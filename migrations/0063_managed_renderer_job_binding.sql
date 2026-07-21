-- Extend P93 exact renderer binding for P94-managed jobs with approved spend reservations.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_renderer_job_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    job_row football_brief.generation_jobs%ROWTYPE;
    preflight_row football_brief.renderer_preflight_records%ROWTYPE;
    entry_row football_brief.renderer_catalogue_entries%ROWTYPE;
    reservation_row football_brief.production_spend_reservations%ROWTYPE;
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
       OR job_row.job_type<>'premium_clip'
       OR job_row.provider IS DISTINCT FROM entry_row.provider_key
       OR job_row.model_id IS DISTINCT FROM entry_row.model_key THEN
        RAISE EXCEPTION 'Renderer job does not match the accepted catalogue request';
    END IF;

    IF entry_row.adapter_kind='simulated' THEN
        IF entry_row.provider_key<>'simulated'
           OR job_row.estimated_cost_usd<>0
           OR job_row.reserved_cost_usd<>0 THEN
            RAISE EXCEPTION 'Simulated renderer bindings must remain zero-fee';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO reservation_row
      FROM football_brief.production_spend_reservations
     WHERE generation_job_id=job_row.id;
    IF reservation_row.id IS NULL
       OR reservation_row.status<>'reserved'
       OR reservation_row.renderer_preflight_id IS DISTINCT FROM preflight_row.id
       OR reservation_row.portfolio_content_id IS DISTINCT FROM job_row.portfolio_content_id
       OR reservation_row.content_version IS DISTINCT FROM job_row.content_version
       OR reservation_row.reserved_amount<job_row.estimated_cost_usd
       OR (job_row.input_payload->>'spend_reservation_id') IS DISTINCT FROM reservation_row.id::text THEN
        RAISE EXCEPTION 'Managed renderer binding requires the exact bound approved spend reservation';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
