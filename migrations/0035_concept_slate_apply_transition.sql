-- Permit the single operational transition from approved slate to applied slate.
-- Approved distribution evidence and selected candidate membership remain immutable.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept slates and slate items cannot be deleted';
    END IF;
    IF TG_TABLE_NAME = 'concept_slates' AND OLD.status <> 'draft' THEN
        IF OLD.status = 'approved'
           AND NEW.status = 'applied'
           AND NEW.batch_id IS NOT DISTINCT FROM OLD.batch_id
           AND NEW.version IS NOT DISTINCT FROM OLD.version
           AND NEW.requested_count IS NOT DISTINCT FROM OLD.requested_count
           AND NEW.requested_format_mix IS NOT DISTINCT FROM OLD.requested_format_mix
           AND NEW.requested_pillar_targets IS NOT DISTINCT FROM OLD.requested_pillar_targets
           AND NEW.actual_format_mix IS NOT DISTINCT FROM OLD.actual_format_mix
           AND NEW.actual_pillar_mix IS NOT DISTINCT FROM OLD.actual_pillar_mix
           AND NEW.gap_report IS NOT DISTINCT FROM OLD.gap_report
           AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
           AND NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by
           AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
           AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Approved and applied concept slates are immutable';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
