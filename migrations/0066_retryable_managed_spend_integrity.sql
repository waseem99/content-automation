-- Keep managed reservations active across retryable P87 failures and retain cumulative attempt cost.

BEGIN;

ALTER TABLE football_brief.production_spend_events
DROP CONSTRAINT IF EXISTS production_spend_events_event_check;

ALTER TABLE football_brief.production_spend_events
ADD CONSTRAINT production_spend_events_event_check CHECK (event IN (
    'plan_created','plan_submitted','decision_recorded','reservation_created',
    'reservation_bound','reservation_released','reservation_reconciled',
    'reservation_retry_cost_recorded','route_overridden'
));

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
        SELECT COALESCE(sum(
                   CASE WHEN psr.status='reserved'
                        THEN GREATEST(psr.reserved_amount,psr.actual_amount)
                        ELSE psr.actual_amount END
               ),0)
          INTO monthly_consumed
          FROM football_brief.production_spend_reservations psr
          JOIN football_brief.shot_routing_plans srp ON srp.id=psr.routing_plan_id
          JOIN football_brief.production_budget_policies pbp ON pbp.id=srp.budget_policy_id
         WHERE pbp.brand_id=policy_row.brand_id AND pbp.month_start=policy_row.month_start
           AND psr.status IN ('reserved','reconciled');
        SELECT COALESCE(sum(
                   CASE WHEN status='reserved'
                        THEN GREATEST(reserved_amount,actual_amount)
                        ELSE actual_amount END
               ),0)
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
    IF OLD.status='reserved' AND NEW.status='reserved'
       AND OLD.generation_job_id IS NOT NULL
       AND NEW.generation_job_id IS NOT DISTINCT FROM OLD.generation_job_id
       AND NEW.bound_at IS NOT DISTINCT FROM OLD.bound_at
       AND NEW.actual_amount>=OLD.actual_amount
       AND NEW.overage_amount=GREATEST(NEW.actual_amount-OLD.reserved_amount,0)
       AND NEW.released_at IS NOT DISTINCT FROM OLD.released_at
       AND NEW.reconciled_at IS NOT DISTINCT FROM OLD.reconciled_at THEN
        RETURN NEW;
    END IF;
    IF OLD.status='reserved' AND NEW.status IN ('released','reconciled') THEN
        IF NEW.actual_amount<OLD.actual_amount THEN
            RAISE EXCEPTION 'Spend reservation actual cost cannot decrease';
        END IF;
        IF NEW.status='released' AND NEW.released_at IS NULL THEN RAISE EXCEPTION 'Release timestamp required'; END IF;
        IF NEW.status='reconciled' AND NEW.reconciled_at IS NULL THEN RAISE EXCEPTION 'Reconciliation timestamp required'; END IF;
        NEW.overage_amount:=GREATEST(NEW.actual_amount-OLD.reserved_amount,0);
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid spend reservation transition';
END;
$$;

CREATE OR REPLACE FUNCTION football_brief.reconcile_generation_job_reservation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reservation_row football_brief.production_spend_reservations%ROWTYPE;
    retryable_failure boolean;
BEGIN
    IF NEW.status IS NOT DISTINCT FROM OLD.status OR NEW.job_type<>'premium_clip' THEN RETURN NEW; END IF;
    SELECT * INTO reservation_row FROM football_brief.production_spend_reservations
     WHERE generation_job_id=NEW.id FOR UPDATE;
    IF reservation_row.id IS NULL THEN RETURN NEW; END IF;

    retryable_failure:=NEW.status='failed'
        AND COALESCE((NEW.error_details->>'retryable')::boolean,false)
        AND NEW.attempt_count<NEW.max_attempts;

    IF retryable_failure THEN
        UPDATE football_brief.production_spend_reservations
           SET actual_amount=NEW.actual_cost_usd,
               overage_amount=GREATEST(NEW.actual_cost_usd-reserved_amount,0)
         WHERE id=reservation_row.id AND status='reserved';
        INSERT INTO football_brief.production_spend_events(routing_plan_id,reservation_id,event,actor,details)
        VALUES (reservation_row.routing_plan_id,reservation_row.id,'reservation_retry_cost_recorded','generation-job',
                jsonb_build_object('job_id',NEW.id,'actual_cost_usd',NEW.actual_cost_usd,
                                   'attempt_count',NEW.attempt_count,'status',NEW.status));
        RETURN NEW;
    END IF;

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

COMMIT;
