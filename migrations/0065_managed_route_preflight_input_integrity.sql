-- Bind every managed route to the exact approved local candidate asset used by its P93 quote.
-- Managed routing also requires a known positive external fee; zero-fee work belongs on local routes.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_managed_route_preflight_input()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    plan_row football_brief.shot_routing_plans%ROWTYPE;
    candidate_row football_brief.visual_candidates%ROWTYPE;
    preflight_row football_brief.renderer_preflight_records%ROWTYPE;
    quoted_project_id text;
    quoted_shot_id text;
    quoted_candidate_id text;
    quoted_asset_count integer;
BEGIN
    IF TG_OP <> 'INSERT' OR NEW.route <> 'managed_render' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO plan_row
      FROM football_brief.shot_routing_plans
     WHERE id = NEW.routing_plan_id;
    SELECT * INTO candidate_row
      FROM football_brief.visual_candidates
     WHERE id = NEW.selected_candidate_id;
    SELECT * INTO preflight_row
      FROM football_brief.renderer_preflight_records
     WHERE id = NEW.renderer_preflight_id;

    IF plan_row.id IS NULL
       OR candidate_row.id IS NULL
       OR candidate_row.asset_id IS NULL
       OR preflight_row.id IS NULL
       OR preflight_row.accepted = false THEN
        RAISE EXCEPTION 'Managed routing requires exact approved local candidate and preflight evidence';
    END IF;

    quoted_project_id := preflight_row.request_payload #>> '{request_metadata,visual_project_id}';
    quoted_shot_id := preflight_row.request_payload #>> '{request_metadata,visual_shot_id}';
    quoted_candidate_id := preflight_row.request_payload #>> '{request_metadata,selected_candidate_id}';

    SELECT count(*) INTO quoted_asset_count
      FROM jsonb_array_elements_text(
          COALESCE(preflight_row.request_payload->'input_asset_ids', '[]'::jsonb)
      ) AS quoted_asset(asset_id)
     WHERE quoted_asset.asset_id = candidate_row.asset_id::text;

    IF quoted_project_id IS DISTINCT FROM plan_row.visual_project_id::text
       OR quoted_shot_id IS DISTINCT FROM NEW.visual_shot_id::text
       OR quoted_candidate_id IS DISTINCT FROM NEW.selected_candidate_id::text
       OR quoted_asset_count <> 1 THEN
        RAISE EXCEPTION 'Managed renderer preflight must quote the exact approved local candidate input';
    END IF;

    IF preflight_row.external_fee_possible = false
       OR preflight_row.estimated_cost <= 0 THEN
        RAISE EXCEPTION 'Managed renderer preflight requires a known positive external fee';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER managed_route_preflight_input_valid
BEFORE INSERT ON football_brief.shot_routing_items
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_managed_route_preflight_input();

COMMIT;
