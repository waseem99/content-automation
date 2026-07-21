-- Bind every routed visual input to the exact selected local candidate or managed job output.

BEGIN;

CREATE UNIQUE INDEX final_release_one_visual_per_routing_item_idx
ON football_brief.final_release_inputs(
    release_id,
    ((metadata->>'routing_item_id')::uuid)
)
WHERE role='visual_shot' AND metadata ? 'routing_item_id';

CREATE OR REPLACE FUNCTION football_brief.validate_release_visual_routing_input()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    routing_item_row football_brief.shot_routing_items%ROWTYPE;
    selected_asset_id uuid;
    requested_routing_item uuid;
    requested_visual_shot uuid;
    reservation_status text;
    managed_job_status text;
    managed_artifact_id uuid;
BEGIN
    SELECT * INTO release_row
      FROM football_brief.final_releases
     WHERE id=NEW.release_id;

    IF release_row.routing_plan_id IS NULL OR NEW.role<>'visual_shot' THEN
        RETURN NEW;
    END IF;

    BEGIN
        requested_routing_item := (NEW.metadata->>'routing_item_id')::uuid;
        requested_visual_shot := (NEW.metadata->>'visual_shot_id')::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'Routed visual inputs require valid routing_item_id and visual_shot_id metadata';
    END;

    IF requested_routing_item IS NULL OR requested_visual_shot IS NULL THEN
        RAISE EXCEPTION 'Routed visual inputs require routing_item_id and visual_shot_id metadata';
    END IF;

    SELECT * INTO routing_item_row
      FROM football_brief.shot_routing_items
     WHERE id=requested_routing_item;

    IF routing_item_row.id IS NULL
       OR routing_item_row.routing_plan_id IS DISTINCT FROM release_row.routing_plan_id
       OR routing_item_row.visual_shot_id IS DISTINCT FROM requested_visual_shot THEN
        RAISE EXCEPTION 'Release visual input must map to the exact approved routing item and shot';
    END IF;

    IF routing_item_row.route='managed_render' THEN
        SELECT psr.status,
               gj.status,
               CASE
                   WHEN (gj.output_payload->>'shared_artifact_version_id') ~
                        '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
                   THEN (gj.output_payload->>'shared_artifact_version_id')::uuid
                   ELSE NULL
               END
          INTO reservation_status,managed_job_status,managed_artifact_id
          FROM football_brief.production_spend_reservations psr
          JOIN football_brief.generation_jobs gj ON gj.id=psr.generation_job_id
         WHERE psr.routing_item_id=routing_item_row.id;

        IF reservation_status IS DISTINCT FROM 'reconciled'
           OR managed_job_status IS DISTINCT FROM 'succeeded'
           OR managed_artifact_id IS DISTINCT FROM NEW.artifact_version_id THEN
            RAISE EXCEPTION 'Managed visual input must be the exact reconciled successful job output artifact';
        END IF;
    ELSE
        SELECT asset_id INTO selected_asset_id
          FROM football_brief.visual_candidates
         WHERE id=routing_item_row.selected_candidate_id;

        IF selected_asset_id IS NULL
           OR NEW.canonical_asset_id IS DISTINCT FROM selected_asset_id THEN
            RAISE EXCEPTION 'Local visual input must use the exact selected routing candidate asset';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
