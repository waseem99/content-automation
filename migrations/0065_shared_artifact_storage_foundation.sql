-- Backend-neutral shared artifact storage, signed review access, retention, and restore evidence.
-- Media bytes remain outside PostgreSQL. Backend credentials remain in external secret providers.

BEGIN;

CREATE TABLE football_brief.shared_storage_backends (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backend_key text NOT NULL UNIQUE CHECK (backend_key ~ '^[a-z0-9][a-z0-9._-]{1,99}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 2 AND 200),
    driver text NOT NULL CHECK (driver IN ('local','s3_compatible')),
    environment text NOT NULL CHECK (environment IN ('development','staging','production','test')),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','retired','unavailable')),
    endpoint_url text,
    bucket_name text,
    base_prefix text NOT NULL DEFAULT '',
    region text,
    credential_secret_ref text,
    public_base_url text,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    activated_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    retired_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    CHECK (driver<>'s3_compatible' OR (bucket_name IS NOT NULL AND credential_secret_ref IS NOT NULL)),
    CHECK (status<>'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)),
    CHECK (status<>'retired' OR (retired_by IS NOT NULL AND retired_at IS NOT NULL)),
    CHECK (credential_secret_ref IS NULL OR credential_secret_ref !~* '(password|secret|token|key)=')
);

CREATE UNIQUE INDEX shared_storage_one_active_environment_idx
ON football_brief.shared_storage_backends(environment,driver)
WHERE status='active';

CREATE TRIGGER shared_storage_backends_touch_updated_at
BEFORE UPDATE ON football_brief.shared_storage_backends
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.shared_storage_objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    backend_id uuid NOT NULL REFERENCES football_brief.shared_storage_backends(id) ON DELETE RESTRICT,
    object_key text NOT NULL CHECK (length(btrim(object_key)) BETWEEN 3 AND 1024),
    storage_uri text NOT NULL,
    object_version text,
    etag text,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes>=0),
    mime_type text,
    status text NOT NULL DEFAULT 'available' CHECK (
        status IN ('uploading','available','missing','quarantined','deletion_pending','deleted')
    ),
    verified_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (asset_id,backend_id,object_key),
    CHECK (status<>'available' OR verified_at IS NOT NULL),
    CHECK (status<>'deleted' OR deleted_at IS NOT NULL)
);

CREATE UNIQUE INDEX shared_storage_object_version_idx
ON football_brief.shared_storage_objects(backend_id,object_key,COALESCE(object_version,''));
CREATE INDEX shared_storage_objects_asset_idx
ON football_brief.shared_storage_objects(asset_id,status);
CREATE INDEX shared_storage_objects_backend_idx
ON football_brief.shared_storage_objects(backend_id,status,object_key);

CREATE TRIGGER shared_storage_objects_touch_updated_at
BEFORE UPDATE ON football_brief.shared_storage_objects
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.shared_artifact_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    portfolio_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer CHECK (content_version IS NULL OR content_version>=1),
    artifact_key text NOT NULL CHECK (length(btrim(artifact_key)) BETWEEN 2 AND 160),
    artifact_kind text NOT NULL CHECK (artifact_kind IN (
        'source','voiceover','keyframe','preview','premium_clip','thumbnail',
        'final_video','package','reference','evidence','other'
    )),
    version integer NOT NULL CHECK (version>=1),
    parent_version_id uuid REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'current' CHECK (
        status IN ('current','superseded','retained','deletion_pending','deleted')
    ),
    original_asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    review_proxy_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    thumbnail_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    retention_until timestamptz,
    legal_hold boolean NOT NULL DEFAULT false,
    legal_hold_reason text,
    legal_hold_set_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    legal_hold_set_at timestamptz,
    superseded_at timestamptz,
    deleted_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_id,artifact_key,version),
    UNIQUE (id,brand_id),
    CHECK (version=1 OR parent_version_id IS NOT NULL),
    CHECK (version<>1 OR parent_version_id IS NULL),
    CHECK (portfolio_content_id IS NOT NULL OR content_version IS NULL),
    CHECK (NOT legal_hold OR (legal_hold_reason IS NOT NULL AND legal_hold_set_by IS NOT NULL AND legal_hold_set_at IS NOT NULL)),
    CHECK (status<>'superseded' OR superseded_at IS NOT NULL),
    CHECK (status<>'deleted' OR deleted_at IS NOT NULL)
);

CREATE UNIQUE INDEX shared_artifact_one_current_idx
ON football_brief.shared_artifact_versions(brand_id,artifact_key)
WHERE status='current';
CREATE INDEX shared_artifact_content_idx
ON football_brief.shared_artifact_versions(portfolio_content_id,content_version,status);

CREATE TRIGGER shared_artifact_versions_touch_updated_at
BEFORE UPDATE ON football_brief.shared_artifact_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.shared_artifact_object_roles (
    artifact_version_id uuid NOT NULL REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    storage_object_id uuid NOT NULL REFERENCES football_brief.shared_storage_objects(id) ON DELETE RESTRICT,
    role text NOT NULL CHECK (role IN ('original','review_proxy','thumbnail')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (artifact_version_id,role),
    UNIQUE (artifact_version_id,storage_object_id)
);

CREATE TABLE football_brief.shared_access_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_version_id uuid NOT NULL REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    storage_object_id uuid NOT NULL REFERENCES football_brief.shared_storage_objects(id) ON DELETE RESTRICT,
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    issued_to_operator_id text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    access_purpose text NOT NULL DEFAULT 'review' CHECK (access_purpose IN ('review','download','restore_verification')),
    token_digest char(64) NOT NULL UNIQUE CHECK (token_digest ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    revoked_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at>created_at),
    CHECK (revoked_at IS NULL OR revoked_by IS NOT NULL)
);

CREATE INDEX shared_access_grants_expiry_idx
ON football_brief.shared_access_grants(expires_at)
WHERE revoked_at IS NULL;

CREATE TABLE football_brief.shared_access_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id uuid NOT NULL REFERENCES football_brief.shared_access_grants(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN ('issued','accessed','expired','revoked','denied')),
    remote_address_hash char(64),
    user_agent_hash char(64),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX shared_access_events_grant_idx
ON football_brief.shared_access_events(grant_id,created_at,id);

CREATE TABLE football_brief.shared_backup_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backend_id uuid NOT NULL REFERENCES football_brief.shared_storage_backends(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'prepared' CHECK (status IN ('prepared','verified','failed')),
    artifact_count integer NOT NULL CHECK (artifact_count>=0),
    object_count integer NOT NULL CHECK (object_count>=0),
    total_size_bytes bigint NOT NULL CHECK (total_size_bytes>=0),
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    manifest_sha256 char(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    failed_at timestamptz,
    CHECK (status<>'verified' OR verified_at IS NOT NULL),
    CHECK (status<>'failed' OR failed_at IS NOT NULL)
);

CREATE TABLE football_brief.shared_restore_verifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id uuid NOT NULL REFERENCES football_brief.shared_backup_snapshots(id) ON DELETE RESTRICT,
    source_storage_object_id uuid NOT NULL REFERENCES football_brief.shared_storage_objects(id) ON DELETE RESTRICT,
    restored_uri text NOT NULL,
    expected_sha256 char(64) NOT NULL CHECK (expected_sha256 ~ '^[0-9a-f]{64}$'),
    observed_sha256 char(64),
    metadata_matches boolean NOT NULL,
    checksum_matches boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('verified','failed')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    verified_by text NOT NULL,
    verified_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_id,source_storage_object_id)
);

CREATE TABLE football_brief.shared_storage_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    backend_id uuid REFERENCES football_brief.shared_storage_backends(id) ON DELETE RESTRICT,
    storage_object_id uuid REFERENCES football_brief.shared_storage_objects(id) ON DELETE RESTRICT,
    artifact_version_id uuid REFERENCES football_brief.shared_artifact_versions(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'backend_created','backend_activated','object_registered','object_verified',
        'artifact_version_created','artifact_superseded','legal_hold_set','legal_hold_released',
        'deletion_requested','object_deleted','backup_prepared','restore_verified','restore_failed'
    )),
    actor text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX shared_storage_events_artifact_idx
ON football_brief.shared_storage_events(artifact_version_id,created_at,id);

COMMENT ON TABLE football_brief.shared_storage_objects IS
    'Backend-neutral object locators and checksums. Media bytes and credentials remain outside PostgreSQL.';
COMMENT ON TABLE football_brief.shared_artifact_versions IS
    'Versioned original/proxy/thumbnail group with retention and legal-hold controls.';
COMMENT ON TABLE football_brief.shared_access_grants IS
    'Time-limited bearer access. Only token digests are stored.';
COMMENT ON TABLE football_brief.shared_backup_snapshots IS
    'Immutable metadata/checksum manifest used to verify database and object restoration together.';

COMMIT;
