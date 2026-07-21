-- Bind release visual inputs to the approved P94 plan and require settled successful managed routes.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_release_visual_routing_input()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    routing_item_row football_brief.shot_routing_items%ROWTYPE;
    requested_routing_item uuid;
    requested_visual_shot uuid;
BEGIN
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.release_id;
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
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_visual_routing_input_valid
BEFORE INSERT ON football_brief.final_release_inputs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_release_visual_routing_input();

CREATE OR REPLACE FUNCTION football_brief.require_complete_release_routing_before_assembly()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    route_count integer;
    mapped_count integer;
    invalid_managed integer;
BEGIN
    IF NOT (OLD.status='draft' AND NEW.status='assembly_queued') OR OLD.routing_plan_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT count(*) INTO route_count
      FROM football_brief.shot_routing_items
     WHERE routing_plan_id=OLD.routing_plan_id;

    SELECT count(DISTINCT (fri.metadata->>'routing_item_id')::uuid) INTO mapped_count
      FROM football_brief.final_release_inputs fri
     WHERE fri.release_id=OLD.id
       AND fri.role='visual_shot'
       AND fri.metadata ? 'routing_item_id';

    IF route_count=0 OR mapped_count<>route_count THEN
        RAISE EXCEPTION 'Every approved routing item requires one exact visual release input';
    END IF;

    SELECT count(*) INTO invalid_managed
      FROM football_brief.shot_routing_items sri
      LEFT JOIN football_brief.production_spend_reservations psr
        ON psr.routing_item_id=sri.id
      LEFT JOIN football_brief.generation_jobs gj
        ON gj.id=psr.generation_job_id
     WHERE sri.routing_plan_id=OLD.routing_plan_id
       AND sri.route='managed_render'
       AND (
           psr.id IS NULL
           OR psr.status<>'reconciled'
           OR gj.id IS NULL
           OR gj.status<>'succeeded'
       );

    IF invalid_managed<>0 THEN
        RAISE EXCEPTION 'Managed routing items must have reconciled successful generation jobs before assembly';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_routing_complete_before_assembly
BEFORE UPDATE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.require_complete_release_routing_before_assembly();

COMMIT;
