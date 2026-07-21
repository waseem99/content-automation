-- Fail-closed shared object lineage, artifact versioning, signed access, retention, and restore evidence.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_shared_storage_backend()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shared storage backends cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN RETURN NEW; END IF;
    IF NEW.backend_key IS DISTINCT FROM OLD.backend_key
       OR NEW.display_name IS DISTINCT FROM OLD.display_name
       OR NEW.driver IS DISTINCT FROM OLD.driver
       OR NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.endpoint_url IS DISTINCT FROM OLD.endpoint_url
       OR NEW.bucket_name IS DISTINCT FROM OLD.bucket_name
       OR NEW.base_prefix IS DISTINCT FROM OLD.base_prefix
       OR NEW.region IS DISTINCT FROM OLD.region
       OR NEW.credential_secret_ref IS DISTINCT FROM OLD.credential_secret_ref
       OR NEW.public_base_url IS DISTINCT FROM OLD.public_base_url
       OR NEW.configuration IS DISTINCT FROM OLD.configuration
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Shared storage backend configuration is immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='active' THEN
        IF NEW.activated_by IS NULL OR NEW.activated_at IS NULL THEN
            RAISE EXCEPTION 'Backend activation evidence is required';
        END IF;
    ELSIF OLD.status='active' AND NEW.status IN ('unavailable','retired') THEN
        IF NEW.status='retired' AND (NEW.retired_by IS NULL OR NEW.retired_at IS NULL) THEN
            RAISE EXCEPTION 'Backend retirement evidence is required';
        END IF;
    ELSIF OLD.status='unavailable' AND NEW.status IN ('active','retired') THEN
        IF NEW.status='active' AND (NEW.activated_by IS NULL OR NEW.activated_at IS NULL) THEN
            RAISE EXCEPTION 'Backend reactivation evidence is required';
        END IF;
        IF NEW.status='retired' AND (NEW.retired_by IS NULL OR NEW.retired_at IS NULL) THEN
            RAISE EXCEPTION 'Backend retirement evidence is required';
        END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid shared storage backend status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shared_storage_backend_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_storage_backends
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_storage_backend();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_storage_object()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    asset_row football_brief.assets%ROWTYPE;
    backend_status text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shared storage object evidence cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT * INTO asset_row FROM football_brief.assets WHERE id=NEW.asset_id;
        SELECT status INTO backend_status FROM football_brief.shared_storage_backends WHERE id=NEW.backend_id;
        IF asset_row.id IS NULL OR asset_row.sha256 IS DISTINCT FROM NEW.sha256
           OR asset_row.size_bytes IS DISTINCT FROM NEW.size_bytes
           OR (asset_row.mime_type IS NOT NULL AND NEW.mime_type IS DISTINCT FROM asset_row.mime_type) THEN
            RAISE EXCEPTION 'Shared object metadata must match the canonical asset';
        END IF;
        IF backend_status<>'active' THEN RAISE EXCEPTION 'Shared objects require an active backend'; END IF;
        IF NEW.status='available' AND NEW.verified_at IS NULL THEN
            RAISE EXCEPTION 'Available shared objects require checksum verification';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.asset_id IS DISTINCT FROM OLD.asset_id
       OR NEW.backend_id IS DISTINCT FROM OLD.backend_id
       OR NEW.object_key IS DISTINCT FROM OLD.object_key
       OR NEW.storage_uri IS DISTINCT FROM OLD.storage_uri
       OR NEW.object_version IS DISTINCT FROM OLD.object_version
       OR NEW.etag IS DISTINCT FROM OLD.etag
       OR NEW.sha256 IS DISTINCT FROM OLD.sha256
       OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Shared object identity and checksum metadata are immutable';
    END IF;
    IF OLD.status='uploading' AND NEW.status IN ('available','missing','quarantined') THEN NULL;
    ELSIF OLD.status='available' AND NEW.status IN ('missing','quarantined','deletion_pending') THEN NULL;
    ELSIF OLD.status IN ('missing','quarantined') AND NEW.status IN ('available','deletion_pending') THEN NULL;
    ELSIF OLD.status='deletion_pending' AND NEW.status='deleted' THEN
        IF NEW.deleted_at IS NULL THEN RAISE EXCEPTION 'Object deletion timestamp is required'; END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid shared object status transition';
    END IF;
    IF NEW.status='available' AND NEW.verified_at IS NULL THEN
        RAISE EXCEPTION 'Available shared objects require checksum verification';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shared_storage_object_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_storage_objects
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_storage_object();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_artifact_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.shared_artifact_versions%ROWTYPE;
    content_brand uuid;
    content_current_version integer;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shared artifact versions cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.portfolio_content_id IS NOT NULL THEN
            SELECT mp.brand_id,pc.version INTO content_brand,content_current_version
              FROM football_brief.portfolio_content pc
              JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
             WHERE pc.id=NEW.portfolio_content_id;
            IF content_brand IS DISTINCT FROM NEW.brand_id
               OR content_current_version IS DISTINCT FROM NEW.content_version THEN
                RAISE EXCEPTION 'Shared artifact content and brand lineage must match the current content version';
            END IF;
        END IF;
        IF NEW.version>1 THEN
            SELECT * INTO parent_row FROM football_brief.shared_artifact_versions WHERE id=NEW.parent_version_id;
            IF parent_row.id IS NULL
               OR parent_row.brand_id IS DISTINCT FROM NEW.brand_id
               OR parent_row.artifact_key IS DISTINCT FROM NEW.artifact_key
               OR parent_row.version+1<>NEW.version
               OR parent_row.status NOT IN ('current','superseded','retained') THEN
                RAISE EXCEPTION 'Artifact revisions require the immediate current or retained parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.portfolio_content_id IS DISTINCT FROM OLD.portfolio_content_id
       OR NEW.content_version IS DISTINCT FROM OLD.content_version
       OR NEW.artifact_key IS DISTINCT FROM OLD.artifact_key
       OR NEW.artifact_kind IS DISTINCT FROM OLD.artifact_kind
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
       OR NEW.original_asset_id IS DISTINCT FROM OLD.original_asset_id
       OR NEW.review_proxy_asset_id IS DISTINCT FROM OLD.review_proxy_asset_id
       OR NEW.thumbnail_asset_id IS DISTINCT FROM OLD.thumbnail_asset_id
       OR NEW.retention_until IS DISTINCT FROM OLD.retention_until
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Shared artifact identity and version metadata are immutable';
    END IF;
    IF NEW.legal_hold IS DISTINCT FROM OLD.legal_hold THEN
        IF NEW.legal_hold AND (NEW.legal_hold_reason IS NULL OR NEW.legal_hold_set_by IS NULL OR NEW.legal_hold_set_at IS NULL) THEN
            RAISE EXCEPTION 'Legal hold evidence is required';
        END IF;
        IF NOT NEW.legal_hold AND OLD.legal_hold AND NEW.legal_hold_reason IS NOT NULL THEN
            RAISE EXCEPTION 'Released legal holds must clear the active reason';
        END IF;
    ELSIF NEW.legal_hold_reason IS DISTINCT FROM OLD.legal_hold_reason
       OR NEW.legal_hold_set_by IS DISTINCT FROM OLD.legal_hold_set_by
       OR NEW.legal_hold_set_at IS DISTINCT FROM OLD.legal_hold_set_at THEN
        RAISE EXCEPTION 'Legal hold fields change only with the hold state';
    END IF;
    IF OLD.status='current' AND NEW.status='superseded' THEN
        IF NEW.superseded_at IS NULL THEN RAISE EXCEPTION 'Supersession timestamp is required'; END IF;
    ELSIF OLD.status IN ('superseded','retained') AND NEW.status='retained' THEN NULL;
    ELSIF OLD.status IN ('current','superseded','retained') AND NEW.status='deletion_pending' THEN
        IF OLD.legal_hold THEN RAISE EXCEPTION 'Legal hold blocks artifact deletion'; END IF;
        IF OLD.retention_until IS NULL OR OLD.retention_until>now() THEN
            RAISE EXCEPTION 'Retention period blocks artifact deletion';
        END IF;
    ELSIF OLD.status='deletion_pending' AND NEW.status='deleted' THEN
        IF NEW.deleted_at IS NULL THEN RAISE EXCEPTION 'Artifact deletion timestamp is required'; END IF;
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Invalid shared artifact status transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shared_artifact_version_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_artifact_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_artifact_version();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_artifact_object_role()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    artifact_row football_brief.shared_artifact_versions%ROWTYPE;
    object_asset uuid;
    expected_asset uuid;
BEGIN
    IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Artifact object role links are immutable'; END IF;
    SELECT * INTO artifact_row FROM football_brief.shared_artifact_versions WHERE id=NEW.artifact_version_id;
    SELECT asset_id INTO object_asset FROM football_brief.shared_storage_objects
     WHERE id=NEW.storage_object_id AND status='available';
    expected_asset:=CASE NEW.role
        WHEN 'original' THEN artifact_row.original_asset_id
        WHEN 'review_proxy' THEN artifact_row.review_proxy_asset_id
        WHEN 'thumbnail' THEN artifact_row.thumbnail_asset_id
    END;
    IF artifact_row.id IS NULL OR object_asset IS NULL OR expected_asset IS NULL
       OR object_asset IS DISTINCT FROM expected_asset THEN
        RAISE EXCEPTION 'Artifact object role must reference the exact available canonical asset';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER shared_artifact_object_role_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_artifact_object_roles
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_artifact_object_role();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_access_grant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    artifact_brand uuid;
    artifact_status text;
    linked_count integer;
    object_status text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Shared access grant evidence cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN
        SELECT brand_id,status INTO artifact_brand,artifact_status
          FROM football_brief.shared_artifact_versions WHERE id=NEW.artifact_version_id;
        SELECT status INTO object_status FROM football_brief.shared_storage_objects WHERE id=NEW.storage_object_id;
        SELECT count(*) INTO linked_count FROM football_brief.shared_artifact_object_roles
         WHERE artifact_version_id=NEW.artifact_version_id AND storage_object_id=NEW.storage_object_id;
        IF artifact_brand IS DISTINCT FROM NEW.brand_id OR artifact_status='deleted'
           OR object_status<>'available' OR linked_count<>1 THEN
            RAISE EXCEPTION 'Access grants require an available object from the exact artifact version and brand';
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

CREATE TRIGGER shared_access_grant_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_access_grants
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_access_grant();

CREATE OR REPLACE FUNCTION football_brief.reject_shared_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Shared access, restore, and storage event evidence is append-only'; END;
$$;

CREATE TRIGGER shared_access_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.shared_access_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_shared_append_only_mutation();
CREATE TRIGGER shared_restore_verifications_immutable
BEFORE UPDATE OR DELETE ON football_brief.shared_restore_verifications
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_shared_append_only_mutation();
CREATE TRIGGER shared_storage_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.shared_storage_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_shared_append_only_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_shared_backup_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Backup snapshot evidence cannot be deleted'; END IF;
    IF TG_OP='INSERT' THEN RETURN NEW; END IF;
    IF NEW.backend_id IS DISTINCT FROM OLD.backend_id
       OR NEW.artifact_count IS DISTINCT FROM OLD.artifact_count
       OR NEW.object_count IS DISTINCT FROM OLD.object_count
       OR NEW.total_size_bytes IS DISTINCT FROM OLD.total_size_bytes
       OR NEW.manifest IS DISTINCT FROM OLD.manifest
       OR NEW.manifest_sha256 IS DISTINCT FROM OLD.manifest_sha256
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Backup snapshot manifest is immutable';
    END IF;
    IF OLD.status='prepared' AND NEW.status='verified' AND NEW.verified_at IS NOT NULL THEN RETURN NEW; END IF;
    IF OLD.status='prepared' AND NEW.status='failed' AND NEW.failed_at IS NOT NULL THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Invalid backup snapshot status transition';
END;
$$;

CREATE TRIGGER shared_backup_snapshot_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.shared_backup_snapshots
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_shared_backup_snapshot();

COMMIT;
