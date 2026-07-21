-- Correct draft-slate supersession evidence and validate concept lineage relationships.

BEGIN;

ALTER TABLE football_brief.concept_slates
    DROP CONSTRAINT IF EXISTS concept_slate_approval_evidence;

ALTER TABLE football_brief.concept_slates
    ADD CONSTRAINT concept_slate_approval_evidence CHECK (
        status IN ('draft', 'superseded')
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    );

CREATE OR REPLACE FUNCTION football_brief.validate_concept_batch_lineage()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    profile_brand_id uuid;
BEGIN
    SELECT brand_id INTO profile_brand_id
      FROM football_brief.brand_profiles
     WHERE id = NEW.brand_profile_id;
    IF profile_brand_id IS DISTINCT FROM NEW.brand_id THEN
        RAISE EXCEPTION 'Concept generation batch profile must belong to its brand';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_generation_batch_lineage_valid
BEFORE INSERT OR UPDATE ON football_brief.concept_generation_batches
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_concept_batch_lineage();

CREATE OR REPLACE FUNCTION football_brief.validate_concept_candidate_lineage()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    source_batch_id uuid;
BEGIN
    IF NEW.revised_from_candidate_id IS NOT NULL THEN
        SELECT batch_id INTO source_batch_id
          FROM football_brief.concept_candidates
         WHERE id = NEW.revised_from_candidate_id;
        IF source_batch_id IS DISTINCT FROM NEW.batch_id THEN
            RAISE EXCEPTION 'Concept candidate revisions must remain in the same generation batch';
        END IF;
    END IF;
    IF NEW.duplicate_candidate_id IS NOT NULL THEN
        SELECT batch_id INTO source_batch_id
          FROM football_brief.concept_candidates
         WHERE id = NEW.duplicate_candidate_id;
        IF source_batch_id IS DISTINCT FROM NEW.batch_id THEN
            RAISE EXCEPTION 'Candidate duplicate evidence must reference the same generation batch';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_candidate_lineage_valid
BEFORE INSERT OR UPDATE ON football_brief.concept_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_concept_candidate_lineage();

COMMIT;
