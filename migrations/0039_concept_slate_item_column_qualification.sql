-- Qualify candidate columns in the slate-item trigger to avoid PL/pgSQL name collisions.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_item_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_slate_id uuid;
    target_candidate_id uuid;
    slate_status text;
    slate_batch_id uuid;
    candidate_batch_id uuid;
    candidate_status text;
    candidate_accepted_content_id uuid;
    content_plan_id uuid;
    plan_brand_id uuid;
    plan_month date;
    batch_brand_id uuid;
    batch_month date;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept slate items cannot be deleted';
    END IF;

    target_slate_id := NEW.slate_id;
    target_candidate_id := NEW.candidate_id;

    SELECT s.status, s.batch_id, gb.brand_id, gb.month_start
      INTO slate_status, slate_batch_id, batch_brand_id, batch_month
      FROM football_brief.concept_slates s
      JOIN football_brief.concept_generation_batches gb ON gb.id = s.batch_id
     WHERE s.id = target_slate_id
     FOR UPDATE OF s;

    SELECT c.batch_id, c.status, c.accepted_content_id
      INTO candidate_batch_id, candidate_status, candidate_accepted_content_id
      FROM football_brief.concept_candidates c
     WHERE c.id = target_candidate_id;

    IF slate_status IS NULL OR candidate_batch_id IS NULL THEN
        RAISE EXCEPTION 'Concept slate and candidate evidence must exist';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF slate_status <> 'draft'
           OR candidate_batch_id IS DISTINCT FROM slate_batch_id
           OR candidate_status <> 'shortlisted' THEN
            RAISE EXCEPTION 'Draft concept slates may contain only shortlisted candidates from the same batch';
        END IF;
        IF NEW.scheduled_for IS NOT NULL OR NEW.applied_content_id IS NOT NULL THEN
            RAISE EXCEPTION 'Draft concept slate items cannot contain application evidence';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.slate_id IS DISTINCT FROM OLD.slate_id
       OR NEW.candidate_id IS DISTINCT FROM OLD.candidate_id
       OR NEW.rank IS DISTINCT FROM OLD.rank
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Concept slate membership and rank are immutable';
    END IF;

    IF slate_status <> 'approved'
       OR OLD.scheduled_for IS NOT NULL
       OR OLD.applied_content_id IS NOT NULL
       OR NEW.scheduled_for IS NULL
       OR NEW.applied_content_id IS NULL
       OR candidate_status <> 'accepted'
       OR candidate_accepted_content_id IS DISTINCT FROM NEW.applied_content_id THEN
        RAISE EXCEPTION 'Approved slate items may be applied exactly once with accepted content evidence';
    END IF;

    SELECT pc.plan_id, mp.brand_id, mp.month_start
      INTO content_plan_id, plan_brand_id, plan_month
      FROM football_brief.portfolio_content pc
      JOIN football_brief.monthly_content_plans mp ON mp.id = pc.plan_id
     WHERE pc.id = NEW.applied_content_id;

    IF content_plan_id IS NULL
       OR plan_brand_id IS DISTINCT FROM batch_brand_id
       OR plan_month IS DISTINCT FROM batch_month
       OR NEW.scheduled_for < batch_month
       OR NEW.scheduled_for >= (batch_month + INTERVAL '1 month')::date THEN
        RAISE EXCEPTION 'Applied concept slate content must belong to the slate brand and month';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
