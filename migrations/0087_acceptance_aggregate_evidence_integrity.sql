-- Validate the aggregate evidence categories that do not naturally map to a single child row.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_aggregate_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_row football_brief.acceptance_pilot_items%ROWTYPE;
    subject_uuid uuid;
    valid_subject boolean:=false;
    required_roles integer;
    source_count integer;
    unsupported_count integer;
    route_count integer;
    explained_count integer;
    managed_count integer;
    verified_renderer_count integer;
BEGIN
    IF NOT NEW.passed OR NEW.category NOT IN (
        'role_assignment','source_evidence','routing_explanation','renderer_lineage',
        'production_economics'
    ) THEN
        RETURN NEW;
    END IF;
    SELECT * INTO item_row
      FROM football_brief.acceptance_pilot_items
     WHERE id=NEW.pilot_item_id;
    IF item_row.id IS NULL THEN
        RAISE EXCEPTION 'Acceptance aggregate evidence requires a pilot item';
    END IF;

    IF NEW.category='role_assignment' THEN
        IF NEW.subject_id IS DISTINCT FROM ('aggregate:' || NEW.details_digest) THEN
            RAISE EXCEPTION 'Role assignment evidence must use the exact aggregate digest';
        END IF;
        SELECT count(DISTINCT required.role) INTO required_roles
          FROM (VALUES ('admin'),('producer'),('reviewer'),('publisher')) AS required(role)
         WHERE EXISTS (
             SELECT 1
               FROM football_brief.operator_users ou
               JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
               LEFT JOIN football_brief.operator_brand_assignments oba
                 ON oba.operator_user_id=ou.id AND oba.brand_id=item_row.brand_id
              WHERE ou.active AND our.role=required.role
                AND (required.role='admin' OR oba.brand_id=item_row.brand_id)
         );
        IF required_roles<>4 THEN
            RAISE EXCEPTION 'Role assignment evidence requires active Admin, Producer, Reviewer, and Publisher coverage';
        END IF;
        RETURN NEW;
    END IF;

    BEGIN
        subject_uuid:=NEW.subject_id::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'Passed aggregate evidence requires a canonical UUID subject';
    END;

    IF NEW.category='source_evidence' THEN
        SELECT count(DISTINCT ss.id),
               count(DISTINCT sc.id) FILTER (
                   WHERE sc.support_status IN ('unsupported','needs_source')
               )
          INTO source_count,unsupported_count
          FROM football_brief.script_versions sv
          JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id
          LEFT JOIN football_brief.script_sources ss ON ss.script_version_id=sv.id
          LEFT JOIN football_brief.script_claims sc ON sc.script_version_id=sv.id
         WHERE sv.id=subject_uuid
           AND sd.portfolio_content_id=item_row.portfolio_content_id
           AND sv.basis_content_version=item_row.content_version
           AND sv.status='approved';
        valid_subject:=source_count>0 AND unsupported_count=0;
    ELSIF NEW.category='routing_explanation' THEN
        SELECT count(*),count(*) FILTER (WHERE nullif(btrim(sri.rationale),'') IS NOT NULL)
          INTO route_count,explained_count
          FROM football_brief.shot_routing_plans srp
          JOIN football_brief.shot_routing_items sri ON sri.routing_plan_id=srp.id
         WHERE srp.id=subject_uuid
           AND srp.portfolio_content_id=item_row.portfolio_content_id
           AND srp.content_version=item_row.content_version
           AND srp.status='approved';
        valid_subject:=route_count>0 AND route_count=explained_count;
    ELSIF NEW.category='renderer_lineage' THEN
        IF item_row.production_mode='managed_render' THEN
            SELECT count(*),count(*) FILTER (
                       WHERE rpr.accepted AND rce.id IS NOT NULL
                   )
              INTO managed_count,verified_renderer_count
              FROM football_brief.shot_routing_plans srp
              JOIN football_brief.shot_routing_items sri ON sri.routing_plan_id=srp.id
              LEFT JOIN football_brief.renderer_preflight_records rpr
                ON rpr.id=sri.renderer_preflight_id
              LEFT JOIN football_brief.renderer_catalogue_entries rce
                ON rce.id=rpr.renderer_catalogue_entry_id
             WHERE srp.id=subject_uuid
               AND srp.portfolio_content_id=item_row.portfolio_content_id
               AND srp.content_version=item_row.content_version
               AND srp.status='approved'
               AND sri.route='managed_render';
            valid_subject:=managed_count>0 AND managed_count=verified_renderer_count;
        ELSE
            SELECT EXISTS (
                SELECT 1
                  FROM football_brief.visual_projects vp
                 WHERE vp.id=subject_uuid
                   AND vp.portfolio_content_id=item_row.portfolio_content_id
                   AND vp.content_version=item_row.content_version
                   AND vp.status='approved'
                   AND nullif(btrim(vp.provider),'') IS NOT NULL
                   AND nullif(btrim(vp.model_id),'') IS NOT NULL
            ) INTO valid_subject;
        END IF;
    ELSE
        SELECT EXISTS (
            SELECT 1
              FROM football_brief.performance_delivery_observations pdo
             WHERE pdo.id=subject_uuid
               AND pdo.portfolio_content_id=item_row.portfolio_content_id
               AND pdo.content_version=item_row.content_version
               AND pdo.production_cost_usd IS NOT NULL
        ) INTO valid_subject;
    END IF;

    IF NOT valid_subject THEN
        RAISE EXCEPTION 'Passed aggregate acceptance evidence does not match canonical production records';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_aggregate_evidence_valid
BEFORE INSERT ON football_brief.acceptance_pilot_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_aggregate_evidence();

COMMIT;
