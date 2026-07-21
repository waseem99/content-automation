-- Qualify distribution aggregates and counters in concept slate approval/application checks.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    slate_item_total integer;
    invalid_candidate_total integer;
    applied_item_total integer;
    computed_formats jsonb;
    computed_pillars jsonb;
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
          INTO slate_item_total, invalid_candidate_total
          FROM football_brief.concept_slate_items si
          JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
         WHERE si.slate_id = NEW.id;

        SELECT COALESCE(jsonb_object_agg(format_counts.format, format_counts.quantity), '{}'::jsonb)
          INTO computed_formats
          FROM (
              SELECT c.format AS format, count(*)::integer AS quantity
                FROM football_brief.concept_slate_items si
                JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
               WHERE si.slate_id = NEW.id
               GROUP BY c.format
          ) AS format_counts;

        SELECT COALESCE(jsonb_object_agg(pillar_counts.pillar, pillar_counts.quantity), '{}'::jsonb)
          INTO computed_pillars
          FROM (
              SELECT c.pillar AS pillar, count(*)::integer AS quantity
                FROM football_brief.concept_slate_items si
                JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
               WHERE si.slate_id = NEW.id
               GROUP BY c.pillar
          ) AS pillar_counts;

        IF slate_item_total <> NEW.requested_count OR invalid_candidate_total <> 0 THEN
            RAISE EXCEPTION 'Concept slate approval requires the exact shortlisted candidate count';
        END IF;
        IF computed_formats IS DISTINCT FROM NEW.actual_format_mix
           OR computed_pillars IS DISTINCT FROM NEW.actual_pillar_mix
           OR computed_formats IS DISTINCT FROM NEW.requested_format_mix
           OR computed_pillars IS DISTINCT FROM NEW.requested_pillar_targets THEN
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
          INTO slate_item_total, applied_item_total
          FROM football_brief.concept_slate_items si
          JOIN football_brief.concept_candidates c ON c.id = si.candidate_id
         WHERE si.slate_id = NEW.id;
        IF slate_item_total <> NEW.requested_count OR applied_item_total <> slate_item_total THEN
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

COMMIT;
