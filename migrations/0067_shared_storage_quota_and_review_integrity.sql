-- Backend quota enforcement and fail-closed review-proxy access.

BEGIN;

CREATE TABLE football_brief.shared_storage_quota_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backend_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.shared_storage_backends(id) ON DELETE RESTRICT,
    hard_limit_bytes bigint NOT NULL CHECK (hard_limit_bytes > 0),
    warning_threshold_bytes bigint NOT NULL CHECK (
        warning_threshold_bytes > 0 AND warning_threshold_bytes <= hard_limit_bytes
    ),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
    created_by text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    retired_at timestamptz,
    CHECK (status <> 'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL))
);

COMMENT ON TABLE football_brief.shared_storage_quota_policies IS
    'Serialized backend byte ceilings. Non-deleted shared objects count toward quota.';

CREATE OR REPLACE FUNCTION football_brief.validate_shared_storage_quota_policy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Shared storage quota policies cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        RETURN NEW;
    END IF;
    IF NEW.backend_id IS DISTINCT FROM OLD.backend_id
       OR NEW.hard_limit_bytes IS DISTINCT FROM OLD.hard_limit_bytes
       OR NEW.warning_threshold_bytes IS DISTINCT FROM OLD.warning_threshold_bytes
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Shared storage quota policy limits are immutable';
    END IF;
    IF OLD.status='active' AND NEW.status='retired'
       AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid shared storage quota policy transition';
END;
$$;

CREATE TRIGGER shared_storage_quota_policy_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_storage_quota_policies
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_storage_quota_policy();

CREATE OR REPLACE FUNCTION football_brief.enforce_shared_storage_object_quota()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    quota_row football_brief.shared_storage_quota_policies%ROWTYPE;
    consumed_bytes bigint;
BEGIN
    IF TG_OP<>'INSERT' OR NEW.status='deleted' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO quota_row
      FROM football_brief.shared_storage_quota_policies
     WHERE backend_id=NEW.backend_id AND status='active'
     FOR UPDATE;
    IF quota_row.id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT COALESCE(sum(size_bytes),0)::bigint INTO consumed_bytes
      FROM football_brief.shared_storage_objects
     WHERE backend_id=NEW.backend_id AND status<>'deleted';

    IF consumed_bytes + NEW.size_bytes > quota_row.hard_limit_bytes THEN
        RAISE EXCEPTION 'Shared storage backend quota exceeded';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shared_storage_object_quota_valid
BEFORE INSERT ON football_brief.shared_storage_objects
FOR EACH ROW EXECUTE FUNCTION football_brief.enforce_shared_storage_object_quota();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_access_grant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    artifact_brand uuid;
    artifact_status text;
    linked_count integer;
    object_status text;
    linked_role text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shared access grant evidence cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT brand_id,status INTO artifact_brand,artifact_status
          FROM football_brief.shared_artifact_versions WHERE id=NEW.artifact_version_id;
        SELECT status INTO object_status FROM football_brief.shared_storage_objects WHERE id=NEW.storage_object_id;
        SELECT count(*),min(role) INTO linked_count,linked_role
          FROM football_brief.shared_artifact_object_roles
         WHERE artifact_version_id=NEW.artifact_version_id
           AND storage_object_id=NEW.storage_object_id;
        IF artifact_brand IS DISTINCT FROM NEW.brand_id
           OR artifact_status NOT IN ('current','superseded','retained')
           OR object_status<>'available' OR linked_count<>1 THEN
            RAISE EXCEPTION 'Access grants require an available object from a reviewable artifact version and brand';
        END IF;
        IF NEW.access_purpose='review' AND linked_role<>'review_proxy' THEN
            RAISE EXCEPTION 'Review access requires the completed review proxy';
        END IF;
        IF NEW.expires_at>now()+interval '24 hours' THEN
            RAISE EXCEPTION 'Shared access grants cannot exceed 24 hours';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.artifact_version_id IS DISTINCT FROM OLD.artifact_version_id
       OR NEW.storage_object_id IS DISTINCT FROM OLD.storage_object_id
       OR NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.issued_to_operator_id IS DISTINCT FROM OLD.issued_to_operator_id
       OR NEW.access_purpose IS DISTINCT FROM OLD.access_purpose
       OR NEW.token_digest IS DISTINCT FROM OLD.token_digest
       OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Shared access grant identity and expiry are immutable';
    END IF;
    IF OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL AND NEW.revoked_by IS NOT NULL THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Access grants support only one-time revocation';
END;
$$;

COMMIT;
