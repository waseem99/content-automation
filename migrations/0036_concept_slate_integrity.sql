-- Harden local concept candidate review and slate application evidence.
-- Exact duplicates remain inspectable; approval and application are fail-closed in PostgreSQL.

BEGIN;

ALTER TABLE football_brief.concept_candidates
    DROP CONSTRAINT IF EXISTS concept_candidates_batch_id_concept_fingerprint_key;

CREATE INDEX IF NOT EXISTS concept_candidates_batch_fingerprint_idx
ON football_brief.concept_candidates (batch_id, concept_fingerprint);

CREATE OR REPLACE FUNCTION football_brief.validate_concept_candidate_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    content_plan_id uuid;
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'candidate' AND NEW.status IN ('shortlisted', 'rejected', 'superseded') THEN
            NULL;
        ELSIF OLD.status = 'shortlisted' AND NEW.status IN ('candidate', 'rejected', 'superseded', 'accepted') THEN
            NULL;
        ELSIF OLD.status = 'rejected' AND NEW.status IN ('candidate', 'superseded') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid concept candidate status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF NEW.status IN ('shortlisted', 'rejected', 'accepted', 'superseded')
       AND (NEW.reviewed_by IS NULL OR NEW.reviewed_at IS NULL) THEN
        RAISE EXCEPTION 'Reviewed concept candidate states require reviewer evidence';
    END IF;

    IF NEW.status = 'accepted' THEN
        IF NEW.accepted_plan_id IS NULL OR NEW.accepted_content_id IS NULL THEN
            RAISE EXCEPTION 'Accepted concept candidates require plan and content evidence';
        END IF;
        SELECT plan_id INTO content_plan_id
          FROM football_brief.portfolio_content
         WHERE id = NEW.accepted_content_id;
        IF content_plan_id IS DISTINCT FROM NEW.accepted_plan_id THEN
            RAISE EXCEPTION 'Accepted concept candidate content must belong to the recorded plan';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_candidate_status_transition_valid
BEFORE UPDATE ON football_brief.concept_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_concept_candidate_transition();

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_count integer;
    invalid_candidate_count integer;
    applied_item_count integer;
    actual_formats jsonb;
    actual_pillars jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept slates cannot be deleted';
    END IF;

    IF NEW.batch_id IS DISTINCT FROM OLD.batch_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.requested_count IS DISTINCT FROM OLD.requested_count
       OR NEW.requested_format_mix IS DISTINCT FROM OLD.requested_format_mix
       OR NEW.requested_pillar_targets IS DISTINCT FROM OLD.requested_pillar_targets
       OR NEW.actual_format_mix IS DISTINCT FROM OLD.actual_format_mix
       OR NEW.actual_pillar_mix IS DISTINCT FROM OLD.actual_pillar_mix
       OR NEW.gap_report IS DISTINCT FROM OLD.gap_report
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Concept slate distribution evidence is immutable';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'approved' THEN
        SELECT count(*),
               count(*) FILTER (WHERE c.batch_id <> NEW.batch_id OR c.status <> 'shortlisted')
          INTO item_count, invalid_candidate_count
          FROM football_brief.concept_slate_items si
          JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
         WHERE si.slate_id = NEW.id;

        SELECT COALESCE(jsonb_object_agg(format, item_count), '{}'::jsonb)
          INTO actual_formats
          FROM (
              SELECT c.format, count(*)::integer AS item_count
                FROM football_brief.concept_slate_items si
                JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
               WHERE si.slate_id = NEW.id
               GROUP BY c.format
          ) counts;

        SELECT COALESCE(jsonb_object_agg(pillar, item_count), '{}'::jsonb)
          INTO actual_pillars
          FROM (
              SELECT c.pillar, count(*)::integer AS item_count
                FROM football_brief.concept_slate_items si
                JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
               WHERE si.slate_id = NEW.id
               GROUP BY c.pillar
          ) counts;

        IF item_count <> NEW.requested_count OR invalid_candidate_count <> 0 THEN
            RAISE EXCEPTION 'Concept slate approval requires the exact shortlisted candidate count';
        END IF;
        IF actual_formats IS DISTINCT FROM NEW.actual_format_mix
           OR actual_pillars IS DISTINCT FROM NEW.actual_pillar_mix
           OR actual_formats IS DISTINCT FROM NEW.requested_format_mix
           OR actual_pillars IS DISTINCT FROM NEW.requested_pillar_targets THEN
            RAISE EXCEPTION 'Concept slate approval requires exact requested distributions';
        END IF;
        IF NEW.approved_by IS NULL OR NEW.approved_at IS NULL THEN
            RAISE EXCEPTION 'Approved concept slates require reviewer evidence';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'superseded' THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'approved' AND NEW.status = 'applied' THEN
        IF NEW.approved_by IS DISTINCT FROM OLD.approved_by
           OR NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
            RAISE EXCEPTION 'Concept slate approval evidence is immutable';
        END IF;
        SELECT count(*),
               count(*) FILTER (
                   WHERE si.scheduled_for IS NOT NULL
                     AND si.applied_content_id IS NOT NULL
                     AND c.status = 'accepted'
                     AND c.accepted_content_id = si.applied_content_id
               )
          INTO item_count, applied_item_count
          FROM football_brief.concept_slate_items si
          JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
         WHERE si.slate_id = NEW.id;
        IF item_count <> NEW.requested_count OR applied_item_count <> item_count THEN
            RAISE EXCEPTION 'Concept slate cannot be applied until every item has accepted content evidence';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status
       OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
       OR NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
        RAISE EXCEPTION 'Invalid concept slate transition from % to %', OLD.status, NEW.status;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS concept_slate_item_immutable ON football_brief.concept_slate_items;

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_item_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    slate_status text;
    slate_batch_id uuid;
    candidate_batch_id uuid;
    candidate_status text;
    accepted_content_id uuid;
    content_plan_id uuid;
    plan_brand_id uuid;
    plan_month date;
    batch_brand_id uuid;
    batch_month date;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept slate items cannot be deleted';
    END IF;

    SELECT s.status, s.batch_id, gb.brand_id, gb.month_start
      INTO slate_status, slate_batch_id, batch_brand_id, batch_month
      FROM football_brief.concept_slates s
      JOIN football_brief.concept_generation_batches gb ON gb.id = s.batch_id
     WHERE s.id = COALESCE(NEW.slate_id, OLD.slate_id)
     FOR UPDATE OF s;

    SELECT batch_id, status, accepted_content_id
      INTO candidate_batch_id, candidate_status, accepted_content_id
      FROM football_brief.concept_candidates
     WHERE id = COALESCE(NEW.candidate_id, OLD.candidate_id);

    IF TG_OP = 'INSERT' THEN
        IF slate_status <> 'draft' OR candidate_batch_id IS DISTINCT FROM slate_batch_id
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
       OR accepted_content_id IS DISTINCT FROM NEW.applied_content_id THEN
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

CREATE TRIGGER concept_slate_item_immutable
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.concept_slate_items
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_concept_slate_item_evidence();

CREATE OR REPLACE FUNCTION football_brief.validate_concept_batch_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept generation batches cannot be deleted';
    END IF;
    IF NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.brand_profile_id IS DISTINCT FROM OLD.brand_profile_id
       OR NEW.month_start IS DISTINCT FROM OLD.month_start
       OR NEW.requested_count IS DISTINCT FROM OLD.requested_count
       OR NEW.requested_format_mix IS DISTINCT FROM OLD.requested_format_mix
       OR NEW.requested_pillar_targets IS DISTINCT FROM OLD.requested_pillar_targets
       OR NEW.seed IS DISTINCT FROM OLD.seed
       OR NEW.adapter_mode IS DISTINCT FROM OLD.adapter_mode
       OR NEW.local_model_id IS DISTINCT FROM OLD.local_model_id
       OR NEW.paid_provider_allowed IS DISTINCT FROM OLD.paid_provider_allowed
       OR NEW.input_snapshot IS DISTINCT FROM OLD.input_snapshot
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Concept generation batch inputs are immutable';
    END IF;
    IF NEW.paid_provider_allowed THEN
        RAISE EXCEPTION 'Paid concept generation providers are prohibited';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'generating' AND NEW.status IN ('ready_for_review', 'failed', 'cancelled') THEN
            NULL;
        ELSIF OLD.status = 'ready_for_review' AND NEW.status IN ('reviewing', 'slate_ready', 'cancelled') THEN
            NULL;
        ELSIF OLD.status = 'reviewing' AND NEW.status IN ('ready_for_review', 'slate_ready', 'cancelled') THEN
            NULL;
        ELSIF OLD.status = 'slate_ready' AND NEW.status IN ('reviewing', 'applied', 'cancelled') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid concept generation batch transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_generation_batch_transition_valid
BEFORE UPDATE OR DELETE ON football_brief.concept_generation_batches
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_concept_batch_transition();

COMMIT;
