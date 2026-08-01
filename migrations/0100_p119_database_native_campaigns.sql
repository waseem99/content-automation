-- P119 database-native campaigns and pre-generation autopilot foundation.
-- PostgreSQL is the production system of record. Storage locations are limited
-- to local files and optional Google Drive copies.

BEGIN;

CREATE TABLE football_brief.pre_generation_autopilot_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    policy_key text NOT NULL CHECK (length(btrim(policy_key)) BETWEEN 3 AND 120),
    active boolean NOT NULL DEFAULT false,
    minimum_auto_score numeric(5,2) NOT NULL DEFAULT 70
        CHECK (minimum_auto_score BETWEEN 0 AND 100),
    max_auto_corrections integer NOT NULL DEFAULT 2
        CHECK (max_auto_corrections BETWEEN 0 AND 10),
    automatic_stages text[] NOT NULL DEFAULT ARRAY[
        'concept','script','sources','narration_plan','scene_plan',
        'caption_package','final_generation_package'
    ]::text[],
    hard_block_codes text[] NOT NULL DEFAULT ARRAY[
        'rights_block','safety_block','territory_block','structural_block',
        'source_block','budget_block','system_block'
    ]::text[],
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    retired_at timestamptz,
    UNIQUE (brand_id, version),
    CONSTRAINT pre_generation_autopilot_policy_activation_valid CHECK (
        active = false OR activated_at IS NOT NULL
    ),
    CONSTRAINT pre_generation_autopilot_policy_arrays_nonempty CHECK (
        cardinality(automatic_stages) > 0 AND cardinality(hard_block_codes) > 0
    )
);

CREATE UNIQUE INDEX pre_generation_autopilot_policy_one_active_idx
ON football_brief.pre_generation_autopilot_policies (brand_id)
WHERE active = true;

CREATE INDEX pre_generation_autopilot_policy_history_idx
ON football_brief.pre_generation_autopilot_policies (brand_id, version DESC);

CREATE TABLE football_brief.production_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_key text NOT NULL UNIQUE
        CHECK (campaign_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 3 AND 240),
    description text NOT NULL DEFAULT '' CHECK (length(description) <= 5000),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validating','ready','active','paused','completed','archived'
    )),
    current_version_id uuid,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    completed_at timestamptz,
    archived_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX production_campaigns_brand_status_idx
ON football_brief.production_campaigns (brand_id, status, updated_at DESC);

CREATE TABLE football_brief.production_campaign_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES football_brief.production_campaigns(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','invalid','validated','active','superseded','archived'
    )),
    autopilot_policy_id uuid NOT NULL
        REFERENCES football_brief.pre_generation_autopilot_policies(id) ON DELETE RESTRICT,
    defaults jsonb NOT NULL DEFAULT '{}'::jsonb,
    item_count integer NOT NULL DEFAULT 0 CHECK (item_count >= 0),
    valid_item_count integer NOT NULL DEFAULT 0 CHECK (valid_item_count >= 0),
    invalid_item_count integer NOT NULL DEFAULT 0 CHECK (invalid_item_count >= 0),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    validated_at timestamptz,
    activated_at timestamptz,
    superseded_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (campaign_id, version),
    CONSTRAINT production_campaign_version_counts_valid CHECK (
        valid_item_count + invalid_item_count <= item_count
    )
);

ALTER TABLE football_brief.production_campaigns
    ADD CONSTRAINT production_campaign_current_version_fk
    FOREIGN KEY (current_version_id)
    REFERENCES football_brief.production_campaign_versions(id)
    ON DELETE RESTRICT;

CREATE UNIQUE INDEX production_campaign_versions_one_active_idx
ON football_brief.production_campaign_versions (campaign_id)
WHERE status = 'active';

CREATE INDEX production_campaign_versions_history_idx
ON football_brief.production_campaign_versions (campaign_id, version DESC);

CREATE TABLE football_brief.production_campaign_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_version_id uuid NOT NULL
        REFERENCES football_brief.production_campaign_versions(id) ON DELETE RESTRICT,
    item_key text NOT NULL CHECK (item_key ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$'),
    ordinal integer NOT NULL CHECK (ordinal >= 1),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 240),
    topic text NOT NULL CHECK (length(btrim(topic)) BETWEEN 3 AND 3000),
    objective text NOT NULL DEFAULT '' CHECK (length(objective) <= 2000),
    audience text NOT NULL DEFAULT '' CHECK (length(audience) <= 1000),
    format_name text NOT NULL DEFAULT 'master_video'
        CHECK (length(btrim(format_name)) BETWEEN 2 AND 80),
    primary_platform text NOT NULL CHECK (primary_platform IN (
        'facebook','instagram','tiktok','youtube','youtube_shorts'
    )),
    target_platforms text[] NOT NULL DEFAULT ARRAY['facebook']::text[],
    target_duration_seconds integer NOT NULL DEFAULT 120
        CHECK (target_duration_seconds BETWEEN 10 AND 150),
    short_cut_count integer NOT NULL DEFAULT 0 CHECK (short_cut_count BETWEEN 0 AND 2),
    language text NOT NULL DEFAULT 'en-US' CHECK (length(btrim(language)) BETWEEN 2 AND 40),
    scheduled_for date NOT NULL,
    priority integer NOT NULL DEFAULT 50 CHECK (priority BETWEEN -1000 AND 1000),
    canonical_fingerprint char(64) NOT NULL,
    state text NOT NULL DEFAULT 'draft' CHECK (state IN (
        'draft','valid','invalid','activated','auto_progressing','human_exception',
        'hard_block','ready_for_final_video_generation','superseded','archived'
    )),
    disposition text CHECK (disposition IN (
        'auto_approved','auto_corrected','human_exception','hard_block',
        'ready_for_final_video_generation'
    )),
    validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    portfolio_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_family_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    ready_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (campaign_version_id, item_key),
    UNIQUE (campaign_version_id, ordinal),
    CONSTRAINT production_campaign_item_platforms_valid CHECK (
        cardinality(target_platforms) > 0
        AND primary_platform = ANY(target_platforms)
        AND target_platforms <@ ARRAY[
            'facebook','instagram','tiktok','youtube','youtube_shorts'
        ]::text[]
    ),
    CONSTRAINT production_campaign_item_validation_shape CHECK (
        jsonb_typeof(validation_errors) = 'array'
    )
);

CREATE INDEX production_campaign_items_state_idx
ON football_brief.production_campaign_items
(campaign_version_id, state, priority DESC, ordinal);

CREATE INDEX production_campaign_items_fingerprint_idx
ON football_brief.production_campaign_items
(campaign_version_id, canonical_fingerprint);

CREATE INDEX production_campaign_items_content_idx
ON football_brief.production_campaign_items
(portfolio_content_id, content_family_id)
WHERE portfolio_content_id IS NOT NULL OR content_family_id IS NOT NULL;

CREATE TABLE football_brief.production_campaign_item_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_item_id uuid NOT NULL
        REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (length(btrim(event_type)) BETWEEN 2 AND 120),
    from_state text,
    to_state text,
    actor text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX production_campaign_item_events_timeline_idx
ON football_brief.production_campaign_item_events
(campaign_item_id, created_at, id);

CREATE TABLE football_brief.pre_generation_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_item_id uuid NOT NULL
        REFERENCES football_brief.production_campaign_items(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    status text NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','superseded','archived')),
    package_sha256 char(64) NOT NULL,
    package jsonb NOT NULL,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    superseded_at timestamptz,
    UNIQUE (campaign_item_id, version),
    CONSTRAINT pre_generation_package_object_valid CHECK (jsonb_typeof(package) = 'object')
);

CREATE UNIQUE INDEX pre_generation_packages_one_ready_idx
ON football_brief.pre_generation_packages (campaign_item_id)
WHERE status = 'ready';

CREATE TABLE football_brief.asset_storage_locations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    provider text NOT NULL CHECK (provider IN ('local','google_drive')),
    locator text NOT NULL CHECK (length(btrim(locator)) BETWEEN 3 AND 4000),
    status text NOT NULL DEFAULT 'available' CHECK (status IN (
        'available','uploading','missing','checksum_mismatch','archived'
    )),
    sha256 char(64) NOT NULL,
    size_bytes bigint CHECK (size_bytes IS NULL OR size_bytes >= 0),
    verified_at timestamptz,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (provider, locator),
    UNIQUE (asset_id, provider, locator)
);

CREATE INDEX asset_storage_locations_asset_idx
ON football_brief.asset_storage_locations (asset_id, status, provider);

COMMENT ON TABLE football_brief.production_campaigns IS
    'Database-native campaign control plane. External sheets and Drive folders are not workflow state.';
COMMENT ON TABLE football_brief.pre_generation_autopilot_policies IS
    'Versioned automatic progression policy through ready_for_final_video_generation.';
COMMENT ON TABLE football_brief.asset_storage_locations IS
    'Permitted physical locations for canonical assets: local system or Google Drive only.';

COMMIT;
