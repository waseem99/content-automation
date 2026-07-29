-- P113 model-use policies are versioned. Active policies may only be retired;
-- their legal evidence and permissions cannot be edited in place.

BEGIN;

DROP TRIGGER IF EXISTS video_model_use_policy_append_only
ON football_brief.video_model_use_policies;

CREATE OR REPLACE FUNCTION football_brief.validate_video_model_use_policy_lineage()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.video_model_use_policies%ROWTYPE;
BEGIN
    IF NEW.version = 1 THEN
        IF NEW.parent_policy_id IS NOT NULL THEN
            RAISE EXCEPTION 'First model-use policy version cannot have a parent';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.parent_policy_id IS NULL THEN
        RAISE EXCEPTION 'Model-use policy child version requires a parent';
    END IF;

    SELECT * INTO parent_row
      FROM football_brief.video_model_use_policies
     WHERE id=NEW.parent_policy_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Model-use policy parent does not exist';
    END IF;
    IF parent_row.provider_key IS DISTINCT FROM NEW.provider_key
       OR parent_row.model_key IS DISTINCT FROM NEW.model_key THEN
        RAISE EXCEPTION 'Model-use policy parent must belong to the same provider and model';
    END IF;
    IF parent_row.version IS DISTINCT FROM NEW.version - 1 THEN
        RAISE EXCEPTION 'Model-use policy parent must be the immediate previous version';
    END IF;
    IF parent_row.status IS DISTINCT FROM 'retired' THEN
        RAISE EXCEPTION 'Model-use policy parent must be retired before child activation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER video_model_use_policy_lineage_valid
BEFORE INSERT OR UPDATE ON football_brief.video_model_use_policies
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_video_model_use_policy_lineage();

CREATE OR REPLACE FUNCTION football_brief.validate_video_model_use_policy_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Video model-use policies cannot be deleted';
    END IF;

    IF NEW.provider_key IS DISTINCT FROM OLD.provider_key
       OR NEW.model_key IS DISTINCT FROM OLD.model_key
       OR NEW.model_display_name IS DISTINCT FROM OLD.model_display_name
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_policy_id IS DISTINCT FROM OLD.parent_policy_id
       OR NEW.license_name IS DISTINCT FROM OLD.license_name
       OR NEW.license_spdx IS DISTINCT FROM OLD.license_spdx
       OR NEW.terms_url IS DISTINCT FROM OLD.terms_url
       OR NEW.evidence_digest IS DISTINCT FROM OLD.evidence_digest
       OR NEW.evidence_recorded_at IS DISTINCT FROM OLD.evidence_recorded_at
       OR NEW.commercial_use_allowed IS DISTINCT FROM OLD.commercial_use_allowed
       OR NEW.allowed_use_scopes IS DISTINCT FROM OLD.allowed_use_scopes
       OR NEW.allowed_territories IS DISTINCT FROM OLD.allowed_territories
       OR NEW.prohibited_territories IS DISTINCT FROM OLD.prohibited_territories
       OR NEW.requires_written_clearance IS DISTINCT FROM OLD.requires_written_clearance
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Video model-use policy evidence is immutable; create a child version';
    END IF;

    IF OLD.status = 'retired' THEN
        RAISE EXCEPTION 'Retired video model-use policies are immutable';
    END IF;

    IF OLD.status = 'active' THEN
        IF NEW.status IS DISTINCT FROM 'retired'
           OR NEW.retired_by IS NULL
           OR NEW.retired_at IS NULL
           OR NEW.activated_by IS DISTINCT FROM OLD.activated_by
           OR NEW.activated_at IS DISTINCT FROM OLD.activated_at THEN
            RAISE EXCEPTION 'Active video model-use policies may only be retired';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER video_model_use_policy_update_valid
BEFORE UPDATE OR DELETE ON football_brief.video_model_use_policies
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_video_model_use_policy_update();

COMMIT;
