-- Fail-closed routing lineage, independent approval, concurrent budget reservations, and job reconciliation.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_production_budget_policy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE parent_row football_brief.production_budget_policies%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Production budget policies cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.production_budget_policies WHERE id=NEW.parent_policy_id;
            IF parent_row.id IS NULL
               OR parent_row.brand_id IS DISTINCT FROM NEW.brand_id
               OR parent_row.month_start IS DISTINCT FROM NEW.month_start
               OR parent_row.version+1<>NEW.version
               OR parent_row.status NOT IN ('active','retired') THEN
                RAISE EXCEPTION 'Budget policy revisions require the immediate active or retired parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('active','retired') THEN
        IF OLD.status='active' AND NEW.status='retired'
           AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL
           AND NEW.brand_id IS NOT DISTINCT FROM OLD.brand_id
           AND NEW.month_start IS NOT DISTINCT FROM OLD.month_start
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.parent_policy_id IS NOT DISTINCT FROM OLD.parent_policy_id
           AND NEW.currency IS NOT DISTINCT FROM OLD.currency
           AND NEW.monthly_soft_limit IS NOT DISTINCT FROM OLD.monthly_soft_limit
           AND NEW.monthly_hard_limit IS NOT DISTINCT FROM OLD.monthly_hard_limit
           AND NEW.default_content_limit IS NOT DISTINCT FROM OLD.default_content_limit
           AND NEW.approval_threshold IS NOT DISTINCT FROM OLD.approval_threshold
           AND NEW.require_approval_for_managed IS NOT DISTINCT FROM OLD.require_approval_for_managed
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.activated_by IS NOT DISTINCT FROM OLD.activated_by
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
           AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Active and retired budget policies are immutable';
    END IF;
    IF NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.month_start IS DISTINCT FROM OLD.month_start
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_policy_id IS DISTINCT FROM OLD.parent_policy_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Budget policy identity is immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='active' THEN
        IF NEW.activated_by IS NULL OR NEW.activated_at IS NULL THEN
            RAISE EXCEPTION 'Budget policy activation evidence is required';
        END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid budget policy status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_budget_policy_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.production_budget_policies
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_production_budget_policy();

CREATE OR REPLACE FUNCTION football_brief.validate_shot_routing_plan()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    lineage_count integer;
    parent_row football_brief.shot_routing_plans%ROWTYPE;
    shot_count integer;
    item_count integer;
    managed_count integer;
    local_count integer;
    manual_count integer;
    estimate numeric(14,6);
    decision_count integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shot routing plans cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT count(*) INTO lineage_count
          FROM football_brief.portfolio_content pc
          JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
          JOIN football_brief.visual_projects vp ON vp.id=NEW.visual_project_id
          JOIN football_brief.production_budget_policies pbp ON pbp.id=NEW.budget_policy_id
         WHERE pc.id=NEW.portfolio_content_id
           AND pc.version=NEW.content_version
           AND vp.portfolio_content_id=pc.id
           AND vp.content_version=NEW.content_version
           AND vp.status='approved'
           AND pbp.brand_id=mp.brand_id
           AND pbp.month_start=mp.month_start
           AND pbp.status='active';
        IF lineage_count<>1 THEN
            RAISE EXCEPTION 'Routing plans require current content, approved visual project, and active matching monthly policy';
        END IF;
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.shot_routing_plans WHERE id=NEW.parent_plan_id;
            IF parent_row.id IS NULL
               OR parent_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
               OR parent_row.content_version IS DISTINCT FROM NEW.content_version
               OR parent_row.version+1<>NEW.version
               OR parent_row.status NOT IN ('approved','changes_requested','rejected','superseded') THEN
                RAISE EXCEPTION 'Routing revisions require the immediate terminal parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.visual_project_id IS DISTINCT FROM OLD.visual_project_id
       OR NEW.budget_policy_id IS DISTINCT FROM OLD.budget_policy_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_plan_id IS DISTINCT FROM OLD.parent_plan_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Routing plan identity is immutable';
    END IF;
    IF NEW.lock_version<>OLD.lock_version+1 THEN
        RAISE EXCEPTION 'Routing plan updates must increment lock_version by exactly one';
    END IF;
    IF OLD.status IN ('approved','rejected','superseded') THEN
        IF OLD.status='approved' AND NEW.status='superseded' THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'Terminal routing plans are immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='in_review' THEN
        SELECT count(*) INTO shot_count FROM football_brief.visual_shots WHERE visual_project_id=NEW.visual_project_id;
        SELECT count(*),
               count(*) FILTER (WHERE route='managed_render'),
               count(*) FILTER (WHERE route IN ('local_render','deterministic_animation')),
               count(*) FILTER (WHERE route='manual_edit'),
               COALESCE(sum(estimated_cost),0)
          INTO item_count,managed_count,local_count,manual_count,estimate
          FROM football_brief.shot_routing_items WHERE routing_plan_id=NEW.id;
        IF shot_count=0 OR item_count<>shot_count THEN
            RAISE EXCEPTION 'Every approved visual shot requires exactly one routing item';
        END IF;
        NEW.managed_shot_count:=managed_count;
        NEW.local_shot_count:=local_count;
        NEW.manual_shot_count:=manual_count;
        NEW.total_estimated_cost:=estimate;
        NEW.submitted_at:=COALESCE(NEW.submitted_at,now());
    ELSIF OLD.status='in_review' AND NEW.status IN ('approved','changes_requested','rejected') THEN
        SELECT count(*) INTO decision_count
          FROM football_brief.production_spend_decisions psd
         WHERE psd.routing_plan_id=NEW.id
           AND psd.decision=NEW.status
           AND psd.plan_lock_version=OLD.lock_version;
        IF decision_count<>1 THEN RAISE EXCEPTION 'Routing decision must match the exact submitted lock'; END IF;
        NEW.decided_at:=COALESCE(NEW.decided_at,now());
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid routing plan status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shot_routing_plan_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shot_routing_plans
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shot_routing_plan();

CREATE OR REPLACE FUNCTION football_brief.validate_shot_routing_item()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    plan_row football_brief.shot_routing_plans%ROWTYPE;
    visual_count integer;
    preflight_row football_brief.renderer_preflight_records%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Routing items are immutable; create a child routing plan'; END IF;
    SELECT * INTO plan_row FROM football_brief.shot_routing_plans WHERE id=NEW.routing_plan_id FOR UPDATE;
    IF plan_row.id IS NULL OR plan_row.status<>'draft' THEN RAISE EXCEPTION 'Routing items require a draft plan'; END IF;
    SELECT count(*) INTO visual_count
      FROM football_brief.visual_shots vs
      JOIN football_brief.visual_candidates vc ON vc.id=NEW.selected_candidate_id
     WHERE vs.id=NEW.visual_shot_id
       AND vs.visual_project_id=plan_row.visual_project_id
       AND vs.status='approved'
       AND vs.selected_candidate_id=vc.id
       AND vc.status='selected';
    IF NEW.route='managed_render' THEN
        IF visual_count<>1 THEN RAISE EXCEPTION 'Managed routing requires the exact approved local candidate'; END IF;
        SELECT * INTO preflight_row FROM football_brief.renderer_preflight_records WHERE id=NEW.renderer_preflight_id;
        IF preflight_row.id IS NULL
           OR preflight_row.accepted=false
           OR preflight_row.portfolio_content_id IS DISTINCT FROM plan_row.portfolio_content_id
           OR preflight_row.content_version IS DISTINCT FROM plan_row.content_version
           OR preflight_row.estimated_cost IS DISTINCT FROM NEW.estimated_cost THEN
            RAISE EXCEPTION 'Managed routing requires the exact accepted renderer preflight and estimate';
        END IF;
    ELSE
        SELECT count(*) INTO visual_count FROM football_brief.visual_shots vs
         WHERE vs.id=NEW.visual_shot_id AND vs.visual_project_id=plan_row.visual_project_id AND vs.status='approved';
        IF visual_count<>1 THEN RAISE EXCEPTION 'Routing requires an approved visual shot'; END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shot_routing_item_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shot_routing_items
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shot_routing_item();

CREATE OR REPLACE FUNCTION football_brief.validate_production_spend_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE plan_row football_brief.shot_routing_plans%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Spend decisions are immutable'; END IF;
    SELECT * INTO plan_row FROM football_brief.shot_routing_plans WHERE id=NEW.routing_plan_id FOR UPDATE;
    IF plan_row.id IS NULL OR plan_row.status<>'in_review' THEN RAISE EXCEPTION 'Spend decisions require a plan in review'; END IF;
    IF NEW.plan_lock_version<>plan_row.lock_version THEN RAISE EXCEPTION 'Spend decision lock is stale'; END IF;
    IF NEW.reviewer_operator_id=plan_row.last_edited_by THEN RAISE EXCEPTION 'Independent spend review is required'; END IF;
    IF NEW.decision='approved' AND NEW.approved_ceiling<plan_row.total_estimated_cost THEN
        RAISE EXCEPTION 'Approved ceiling cannot be below the routed estimate';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_spend_decision_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.production_spend_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_production_spend_decision();

CREATE OR REPLACE FUNCTION football_brief.apply_production_spend_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE football_brief.shot_routing_plans
       SET status=NEW.decision,decided_at=now(),lock_version=lock_version+1
     WHERE id=NEW.routing_plan_id AND status='in_review' AND lock_version=NEW.plan_lock_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'Spend decision could not advance the exact routing plan'; END IF;
    INSERT INTO football_brief.production_spend_events(routing_plan_id,event,actor,details)
    VALUES (NEW.routing_plan_id,'decision_recorded',NEW.reviewer_operator_id,
            jsonb_build_object('decision_id',NEW.id,'decision',NEW.decision,
                               'approved_ceiling',NEW.approved_ceiling));
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_spend_decision_apply
AFTER INSERT ON football_brief.production_spend_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.apply_production_spend_decision();

CREATE OR REPLACE FUNCTION football_brief.validate_production_spend_reservation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    plan_row football_brief.shot_routing_plans%ROWTYPE;
    item_row football_brief.shot_routing_items%ROWTYPE;
    policy_row football_brief.production_budget_policies%ROWTYPE;
    decision_row football_brief.production_spend_decisions%ROWTYPE;
    monthly_consumed numeric(14,6);
    content_consumed numeric(14,6);
    projected_monthly numeric(14,6);
    projected_content numeric(14,6);
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Spend reservations cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT * INTO plan_row FROM football_brief.shot_routing_plans WHERE id=NEW.routing_plan_id;
        SELECT * INTO item_row FROM football_brief.shot_routing_items WHERE id=NEW.routing_item_id;
        SELECT * INTO decision_row FROM football_brief.production_spend_decisions WHERE routing_plan_id=NEW.routing_plan_id;
        SELECT * INTO policy_row FROM football_brief.production_budget_policies
         WHERE id=plan_row.budget_policy_id FOR UPDATE;
        IF plan_row.id IS NULL OR plan_row.status<>'approved'
           OR item_row.id IS NULL OR item_row.routing_plan_id<>plan_row.id
           OR item_row.route<>'managed_render'
           OR decision_row.id IS NULL OR decision_row.decision<>'approved'
           OR policy_row.id IS NULL OR policy_row.status<>'active'
           OR NEW.renderer_preflight_id IS DISTINCT FROM item_row.renderer_preflight_id
           OR NEW.portfolio_content_id IS DISTINCT FROM plan_row.portfolio_content_id
           OR NEW.content_version IS DISTINCT FROM plan_row.content_version
           OR NEW.reserved_amount IS DISTINCT FROM item_row.estimated_cost THEN
            RAISE EXCEPTION 'Reservation requires exact approved routing, quote, policy, and content evidence';
        END IF;
        SELECT COALESCE(sum(CASE WHEN psr.status='reserved' THEN psr.reserved_amount ELSE psr.actual_amount END),0)
          INTO monthly_consumed
          FROM football_brief.production_spend_reservations psr
          JOIN football_brief.shot_routing_plans srp ON srp.id=psr.routing_plan_id
          JOIN football_brief.production_budget_policies pbp ON pbp.id=srp.budget_policy_id
         WHERE pbp.brand_id=policy_row.brand_id AND pbp.month_start=policy_row.month_start
           AND psr.status IN ('reserved','reconciled');
        SELECT COALESCE(sum(CASE WHEN status='reserved' THEN reserved_amount ELSE actual_amount END),0)
          INTO content_consumed
          FROM football_brief.production_spend_reservations
         WHERE portfolio_content_id=NEW.portfolio_content_id
           AND content_version=NEW.content_version
           AND status IN ('reserved','reconciled');
        projected_monthly:=monthly_consumed+NEW.reserved_amount;
        projected_content:=content_consumed+NEW.reserved_amount;
        IF projected_monthly>policy_row.monthly_hard_limit THEN
            RAISE EXCEPTION 'Monthly managed-production hard limit exceeded';
        END IF;
        IF projected_content>decision_row.approved_ceiling THEN
            RAISE EXCEPTION 'Approved content ceiling exceeded';
        END IF;
        IF projected_monthly>policy_row.monthly_soft_limit THEN
            NEW.soft_limit_exceeded:=true;
            NEW.warnings:=jsonb_build_array(jsonb_build_object(
                'code','MONTHLY_SOFT_LIMIT','projected',projected_monthly,
                'limit',policy_row.monthly_soft_limit));
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.routing_plan_id IS DISTINCT FROM OLD.routing_plan_id
       OR NEW.routing_item_id IS DISTINCT FROM OLD.routing_item_id
       OR NEW.renderer_preflight_id IS DISTINCT FROM OLD.renderer_preflight_id
       OR NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.reserved_amount IS DISTINCT FROM OLD.reserved_amount
       OR NEW.soft_limit_exceeded IS DISTINCT FROM OLD.soft_limit_exceeded
       OR NEW.warnings IS DISTINCT FROM OLD.warnings
       OR NEW.reservation_key IS DISTINCT FROM OLD.reservation_key
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Spend reservation identity and quote are immutable';
    END IF;
    IF OLD.status='reserved' AND NEW.status='reserved'
       AND OLD.generation_job_id IS NULL AND NEW.generation_job_id IS NOT NULL
       AND NEW.bound_at IS NOT NULL
       AND NEW.actual_amount=OLD.actual_amount AND NEW.overage_amount=OLD.overage_amount THEN
        RETURN NEW;
    END IF;
    IF OLD.status='reserved' AND NEW.status IN ('released','reconciled') THEN
        IF NEW.status='released' AND NEW.released_at IS NULL THEN RAISE EXCEPTION 'Release timestamp required'; END IF;
        IF NEW.status='reconciled' AND NEW.reconciled_at IS NULL THEN RAISE EXCEPTION 'Reconciliation timestamp required'; END IF;
        NEW.overage_amount:=GREATEST(NEW.actual_amount-OLD.reserved_amount,0);
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid spend reservation transition';
END;
$$;

CREATE TRIGGER production_spend_reservation_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.production_spend_reservations
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_production_spend_reservation();

CREATE OR REPLACE FUNCTION football_brief.validate_managed_generation_job_budget()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reservation_id uuid;
    reservation_row football_brief.production_spend_reservations%ROWTYPE;
    entry_row football_brief.renderer_catalogue_entries%ROWTYPE;
BEGIN
    IF NEW.job_type<>'premium_clip' OR NEW.provider='simulated' THEN RETURN NEW; END IF;
    BEGIN reservation_id:=(NEW.input_payload->>'spend_reservation_id')::uuid;
    EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'Managed production job requires spend_reservation_id'; END;
    SELECT * INTO reservation_row FROM football_brief.production_spend_reservations WHERE id=reservation_id FOR UPDATE;
    SELECT rce.* INTO entry_row
      FROM football_brief.renderer_preflight_records rp
      JOIN football_brief.renderer_catalogue_entries rce ON rce.id=rp.renderer_catalogue_entry_id
     WHERE rp.id=reservation_row.renderer_preflight_id;
    IF reservation_row.id IS NULL OR reservation_row.status<>'reserved'
       OR reservation_row.generation_job_id IS NOT NULL
       OR reservation_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
       OR reservation_row.content_version IS DISTINCT FROM NEW.content_version
       OR NEW.estimated_cost_usd>reservation_row.reserved_amount
       OR entry_row.provider_key IS DISTINCT FROM NEW.provider
       OR entry_row.model_key IS DISTINCT FROM NEW.model_id
       OR entry_row.adapter_kind='simulated' THEN
        RAISE EXCEPTION 'Managed production job does not match an available approved reservation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER managed_generation_job_budget_valid
BEFORE INSERT ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_managed_generation_job_budget();

CREATE OR REPLACE FUNCTION football_brief.reconcile_generation_job_reservation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE reservation_row football_brief.production_spend_reservations%ROWTYPE;
BEGIN
    IF NEW.status IS NOT DISTINCT FROM OLD.status OR NEW.job_type<>'premium_clip' THEN RETURN NEW; END IF;
    SELECT * INTO reservation_row FROM football_brief.production_spend_reservations
     WHERE generation_job_id=NEW.id FOR UPDATE;
    IF reservation_row.id IS NULL THEN RETURN NEW; END IF;
    IF NEW.status='succeeded' THEN
        UPDATE football_brief.production_spend_reservations
           SET status='reconciled',actual_amount=NEW.actual_cost_usd,reconciled_at=now()
         WHERE id=reservation_row.id AND status='reserved';
        INSERT INTO football_brief.production_spend_events(routing_plan_id,reservation_id,event,actor,details)
        VALUES (reservation_row.routing_plan_id,reservation_row.id,'reservation_reconciled','generation-job',
                jsonb_build_object('job_id',NEW.id,'actual_cost_usd',NEW.actual_cost_usd,'status',NEW.status));
    ELSIF NEW.status IN ('failed','cancelled','dead_letter') THEN
        IF NEW.actual_cost_usd>0 THEN
            UPDATE football_brief.production_spend_reservations
               SET status='reconciled',actual_amount=NEW.actual_cost_usd,reconciled_at=now()
             WHERE id=reservation_row.id AND status='reserved';
            INSERT INTO football_brief.production_spend_events(routing_plan_id,reservation_id,event,actor,details)
            VALUES (reservation_row.routing_plan_id,reservation_row.id,'reservation_reconciled','generation-job',
                    jsonb_build_object('job_id',NEW.id,'actual_cost_usd',NEW.actual_cost_usd,'status',NEW.status));
        ELSE
            UPDATE football_brief.production_spend_reservations
               SET status='released',released_at=now()
             WHERE id=reservation_row.id AND status='reserved';
            INSERT INTO football_brief.production_spend_events(routing_plan_id,reservation_id,event,actor,details)
            VALUES (reservation_row.routing_plan_id,reservation_row.id,'reservation_released','generation-job',
                    jsonb_build_object('job_id',NEW.id,'status',NEW.status));
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_job_spend_reconcile
AFTER UPDATE OF status ON football_brief.generation_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.reconcile_generation_job_reservation();

CREATE OR REPLACE FUNCTION football_brief.reject_spend_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Spend decisions and events are append-only'; END; $$;
CREATE TRIGGER production_spend_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_spend_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_spend_evidence_mutation();
CREATE TRIGGER production_spend_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_spend_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_spend_evidence_mutation();

COMMIT;
