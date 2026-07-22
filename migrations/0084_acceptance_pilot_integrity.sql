-- Fail-closed acceptance-pilot scope, evidence, sign-off, and external live-result gates.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_acceptance_pilot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_count integer;
    brand_count integer;
    invalid_brand_count integer;
    local_count integer;
    managed_count integer;
    passed_count integer;
    required_evidence_failures integer;
    operations_evidence_failures integer;
    blocking_defects integer;
    approved_signoffs integer;
    rejected_signoffs integer;
    live_required_count integer;
    live_evidence_count integer;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Acceptance pilots cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.version>1 THEN
            IF NOT EXISTS (
                SELECT 1 FROM football_brief.acceptance_pilots parent
                 WHERE parent.id=NEW.parent_pilot_id
                   AND parent.pilot_key=NEW.pilot_key
                   AND parent.version=NEW.version-1
                   AND parent.status IN ('accepted','retired')
            ) THEN
                RAISE EXCEPTION 'Acceptance pilot revisions require the immediately terminal parent';
            END IF;
        END IF;
        IF COALESCE((NEW.scope->>'items_per_brand')::integer,0)<>2
           OR COALESCE((NEW.scope->>'total_items')::integer,0)<>4
           OR COALESCE(NEW.scope->'brand_slugs','[]'::jsonb) <> '["animal-x","rawr-nation"]'::jsonb THEN
            RAISE EXCEPTION 'P100 scope requires exactly two items each for Animal X and Rawr Nation';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.pilot_key IS DISTINCT FROM OLD.pilot_key
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_pilot_id IS DISTINCT FROM OLD.parent_pilot_id
       OR NEW.scope IS DISTINCT FROM OLD.scope
       OR NEW.acceptance_policy IS DISTINCT FROM OLD.acceptance_policy
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Acceptance pilot identity and policy are immutable';
    END IF;
    IF OLD.status IN ('accepted','retired') THEN
        RAISE EXCEPTION 'Terminal acceptance pilots are immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='running' AND NEW.started_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('running','blocked') AND NEW.status='blocked' THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('running','blocked') AND NEW.status='accepted' THEN
        SELECT count(*),count(DISTINCT api.brand_id),
               count(*) FILTER (WHERE b.slug NOT IN ('rawr-nation','animal-x')),
               count(*) FILTER (WHERE api.production_mode='local_only'),
               count(*) FILTER (WHERE api.production_mode='managed_render'),
               count(*) FILTER (WHERE api.status='passed'),
               count(*) FILTER (WHERE api.live_delivery_evidence_required)
          INTO item_count,brand_count,invalid_brand_count,local_count,managed_count,passed_count,
               live_required_count
          FROM football_brief.acceptance_pilot_items api
          JOIN football_brief.brands b ON b.id=api.brand_id
         WHERE api.pilot_id=NEW.id;
        IF item_count<>4 OR brand_count<>2 OR invalid_brand_count<>0
           OR local_count<1 OR managed_count<1 OR passed_count<>4 THEN
            RAISE EXCEPTION 'Acceptance requires four passed items across both brands with local and managed coverage';
        END IF;
        IF EXISTS (
            SELECT 1 FROM (
                SELECT api.brand_id,count(*) AS count
                  FROM football_brief.acceptance_pilot_items api
                 WHERE api.pilot_id=NEW.id GROUP BY api.brand_id
            ) counts WHERE counts.count<>2
        ) THEN
            RAISE EXCEPTION 'Acceptance requires exactly two items per brand';
        END IF;

        WITH required(category) AS (
            VALUES
              ('brand_profile'),('narration_preset'),('role_assignment'),('concept_approval'),
              ('source_evidence'),('script_approval'),('script_revision'),('narration_approval'),
              ('narration_revision'),('visual_approval'),('visual_revision'),('routing_explanation'),
              ('spend_approval'),('renderer_lineage'),('artifact_lineage'),('final_qa'),
              ('release_manifest'),('publisher_decision'),('staging_delivery'),
              ('analytics_observation'),('production_economics')
        )
        SELECT count(*) INTO required_evidence_failures
          FROM football_brief.acceptance_pilot_items api
          CROSS JOIN required r
         WHERE api.pilot_id=NEW.id
           AND NOT EXISTS (
               SELECT 1 FROM football_brief.acceptance_pilot_evidence ape
                WHERE ape.pilot_item_id=api.id AND ape.category=r.category AND ape.passed
           );
        IF required_evidence_failures<>0 THEN
            RAISE EXCEPTION 'Acceptance requires complete passed evidence for every pilot item';
        END IF;

        WITH required(category) AS (
            VALUES ('backup_restore'),('worker_restart'),('runbook_validation')
        )
        SELECT count(*) INTO operations_evidence_failures
          FROM required r
         WHERE NOT EXISTS (
             SELECT 1 FROM football_brief.acceptance_pilot_evidence ape
             JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
              WHERE api.pilot_id=NEW.id AND ape.category=r.category AND ape.passed
         );
        IF operations_evidence_failures<>0 THEN
            RAISE EXCEPTION 'Acceptance requires restore, restart, and runbook evidence';
        END IF;

        SELECT count(*) INTO blocking_defects
          FROM football_brief.acceptance_pilot_defects
         WHERE pilot_id=NEW.id AND severity IN ('major','critical') AND status='open';
        IF blocking_defects<>0 THEN
            RAISE EXCEPTION 'Unresolved major or critical defects block pilot acceptance';
        END IF;
        SELECT count(*) FILTER (WHERE decision='approved'),count(*) FILTER (WHERE decision='rejected')
          INTO approved_signoffs,rejected_signoffs
          FROM football_brief.acceptance_pilot_signoffs WHERE pilot_id=NEW.id;
        IF approved_signoffs<>3 OR rejected_signoffs<>0 THEN
            RAISE EXCEPTION 'Admin, Reviewer, and Publisher approval are required';
        END IF;
        SELECT count(*) INTO live_evidence_count
          FROM football_brief.acceptance_live_delivery_evidence alde
          JOIN football_brief.acceptance_pilot_items api ON api.id=alde.pilot_item_id
         WHERE alde.pilot_id=NEW.id AND api.live_delivery_evidence_required
           AND alde.result_status IN ('submitted','published');
        IF live_required_count<1 OR live_evidence_count<1 THEN
            RAISE EXCEPTION 'At least one separately signed-off live-delivery result is required';
        END IF;
        IF NEW.accepted_by IS NULL OR NEW.accepted_at IS NULL THEN
            RAISE EXCEPTION 'Pilot acceptance actor and timestamp are required';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('running','blocked') AND NEW.status='retired'
       AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid acceptance pilot transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER acceptance_pilots_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.acceptance_pilots
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_pilot();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_pilot_item()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pilot_row football_brief.acceptance_pilots%ROWTYPE;
    content_brand_id uuid;
    current_version integer;
    brand_slug text;
    brand_items integer;
    total_items integer;
    delivery_row record;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Acceptance pilot items cannot be deleted'; END IF;
    SELECT * INTO pilot_row FROM football_brief.acceptance_pilots WHERE id=NEW.pilot_id FOR UPDATE;
    IF pilot_row.id IS NULL OR pilot_row.status NOT IN ('draft','running','blocked') THEN
        RAISE EXCEPTION 'Pilot items require an editable acceptance pilot';
    END IF;
    IF TG_OP='INSERT' THEN
        SELECT mp.brand_id,pc.version,b.slug
          INTO content_brand_id,current_version,brand_slug
          FROM football_brief.portfolio_content pc
          JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
          JOIN football_brief.brands b ON b.id=mp.brand_id
         WHERE pc.id=NEW.portfolio_content_id;
        IF content_brand_id IS DISTINCT FROM NEW.brand_id
           OR current_version IS DISTINCT FROM NEW.content_version
           OR brand_slug NOT IN ('rawr-nation','animal-x') THEN
            RAISE EXCEPTION 'Pilot item must bind the current exact content version for an approved pilot brand';
        END IF;
        SELECT count(*) INTO brand_items FROM football_brief.acceptance_pilot_items
         WHERE pilot_id=NEW.pilot_id AND brand_id=NEW.brand_id;
        SELECT count(*) INTO total_items FROM football_brief.acceptance_pilot_items
         WHERE pilot_id=NEW.pilot_id;
        IF brand_items>=2 OR total_items>=4 THEN
            RAISE EXCEPTION 'Pilot scope permits exactly two items per brand and four total';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.pilot_id IS DISTINCT FROM OLD.pilot_id
       OR NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.production_mode IS DISTINCT FROM OLD.production_mode
       OR NEW.required_revision_stages IS DISTINCT FROM OLD.required_revision_stages
       OR NEW.live_delivery_evidence_required IS DISTINCT FROM OLD.live_delivery_evidence_required
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Pilot item identity and acceptance requirements are immutable';
    END IF;
    IF NEW.staging_delivery_request_id IS NOT DISTINCT FROM OLD.staging_delivery_request_id
       AND NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;
    IF NEW.staging_delivery_request_id IS NOT NULL THEN
        SELECT pdr.status,pdt.environment,pdt.simulated,fr.portfolio_content_id,fr.content_version
          INTO delivery_row
          FROM football_brief.platform_delivery_requests pdr
          JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
          JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
         WHERE pdr.id=NEW.staging_delivery_request_id;
        IF delivery_row.status<>'succeeded' OR delivery_row.environment<>'staging'
           OR NOT delivery_row.simulated
           OR delivery_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
           OR delivery_row.content_version IS DISTINCT FROM NEW.content_version THEN
            RAISE EXCEPTION 'Pilot staging delivery must be a succeeded simulated delivery of the exact content version';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acceptance_pilot_items_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.acceptance_pilot_items
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_pilot_item();

CREATE OR REPLACE FUNCTION football_brief.protect_acceptance_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Acceptance evidence and events are append-only';
END;
$$;

CREATE TRIGGER acceptance_pilot_evidence_immutable
BEFORE UPDATE OR DELETE ON football_brief.acceptance_pilot_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_append_only();
CREATE TRIGGER acceptance_pilot_signoffs_immutable
BEFORE UPDATE OR DELETE ON football_brief.acceptance_pilot_signoffs
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_append_only();
CREATE TRIGGER acceptance_live_delivery_evidence_immutable
BEFORE UPDATE OR DELETE ON football_brief.acceptance_live_delivery_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_append_only();
CREATE TRIGGER acceptance_pilot_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.acceptance_pilot_events
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_acceptance_append_only();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_defect()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Acceptance defects cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN RETURN NEW; END IF;
    IF NEW.pilot_id IS DISTINCT FROM OLD.pilot_id
       OR NEW.pilot_item_id IS DISTINCT FROM OLD.pilot_item_id
       OR NEW.defect_key IS DISTINCT FROM OLD.defect_key
       OR NEW.severity IS DISTINCT FROM OLD.severity
       OR NEW.summary IS DISTINCT FROM OLD.summary
       OR NEW.evidence IS DISTINCT FROM OLD.evidence
       OR NEW.opened_by IS DISTINCT FROM OLD.opened_by
       OR NEW.opened_at IS DISTINCT FROM OLD.opened_at THEN
        RAISE EXCEPTION 'Acceptance defect identity is immutable';
    END IF;
    IF OLD.status='open' AND NEW.status IN ('resolved','waived')
       AND NEW.resolved_by IS NOT NULL AND NEW.resolved_at IS NOT NULL
       AND NEW.resolution IS NOT NULL THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Invalid acceptance defect transition';
END;
$$;
CREATE TRIGGER acceptance_pilot_defects_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.acceptance_pilot_defects
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_defect();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_signoff()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actual_role boolean;
    item_count integer;
    passed_count integer;
    blocking_defects integer;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Acceptance sign-offs are append-only'; END IF;
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.operator_id AND ou.active AND our.role=NEW.signoff_role
    ) INTO actual_role;
    IF NOT actual_role THEN RAISE EXCEPTION 'Sign-off operator must hold the recorded role'; END IF;
    SELECT count(*),count(*) FILTER (WHERE status='passed') INTO item_count,passed_count
      FROM football_brief.acceptance_pilot_items WHERE pilot_id=NEW.pilot_id;
    SELECT count(*) INTO blocking_defects FROM football_brief.acceptance_pilot_defects
     WHERE pilot_id=NEW.pilot_id AND severity IN ('major','critical') AND status='open';
    IF item_count<>4 OR passed_count<>4 OR blocking_defects<>0 THEN
        RAISE EXCEPTION 'Sign-off requires four passed items and no open major or critical defect';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER acceptance_pilot_signoffs_valid
BEFORE INSERT ON football_brief.acceptance_pilot_signoffs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_signoff();

CREATE OR REPLACE FUNCTION football_brief.validate_acceptance_live_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_row football_brief.acceptance_pilot_items%ROWTYPE;
    release_row football_brief.final_releases%ROWTYPE;
    signoff_count integer;
    is_publisher boolean;
    blocking_defects integer;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Live delivery evidence is append-only'; END IF;
    SELECT * INTO item_row FROM football_brief.acceptance_pilot_items WHERE id=NEW.pilot_item_id;
    SELECT * INTO release_row FROM football_brief.final_releases WHERE id=NEW.final_release_id;
    SELECT count(*) INTO signoff_count FROM football_brief.acceptance_pilot_signoffs
     WHERE pilot_id=NEW.pilot_id AND decision='approved';
    SELECT EXISTS (
        SELECT 1 FROM football_brief.operator_users ou
        JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.recorded_by AND ou.active AND our.role='publisher'
    ) INTO is_publisher;
    SELECT count(*) INTO blocking_defects FROM football_brief.acceptance_pilot_defects
     WHERE pilot_id=NEW.pilot_id AND severity IN ('major','critical') AND status='open';
    IF item_row.id IS NULL OR item_row.pilot_id IS DISTINCT FROM NEW.pilot_id
       OR NOT item_row.live_delivery_evidence_required
       OR release_row.id IS NULL OR release_row.status<>'approved'
       OR release_row.portfolio_content_id IS DISTINCT FROM item_row.portfolio_content_id
       OR release_row.content_version IS DISTINCT FROM item_row.content_version
       OR signoff_count<>3 OR NOT is_publisher OR blocking_defects<>0 THEN
        RAISE EXCEPTION 'Live result evidence requires exact approved release, three sign-offs, Publisher role, and no blocking defects';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER acceptance_live_delivery_evidence_valid
BEFORE INSERT ON football_brief.acceptance_live_delivery_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_acceptance_live_evidence();

COMMIT;
