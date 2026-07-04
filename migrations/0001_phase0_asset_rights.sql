-- Football Brief Phase 0: asset, rights, evidence, and approved voice foundation
-- Target database: PostgreSQL 15+

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS football_brief;

CREATE OR REPLACE FUNCTION football_brief.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE football_brief.assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type text NOT NULL CHECK (asset_type IN (
        'video', 'image', 'audio', 'font', 'document',
        'license_evidence', 'generated_graphic', 'voice'
    )),
    source_type text NOT NULL DEFAULT 'unknown' CHECK (source_type IN (
        'owned', 'commissioned', 'licensed', 'stock', 'creative_commons',
        'public_domain', 'ai_generated', 'client_supplied', 'unknown'
    )),
    lifecycle_status text NOT NULL DEFAULT 'candidate' CHECK (lifecycle_status IN (
        'candidate', 'internal_only', 'approved', 'rejected', 'expired', 'deleted'
    )),
    original_filename text,
    storage_uri text NOT NULL,
    sha256 char(64) NOT NULL UNIQUE,
    mime_type text,
    size_bytes bigint CHECK (size_bytes IS NULL OR size_bytes >= 0),
    parent_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT assets_parent_not_self CHECK (parent_asset_id IS NULL OR parent_asset_id <> id)
);

CREATE INDEX assets_status_type_idx
    ON football_brief.assets (lifecycle_status, asset_type);
CREATE INDEX assets_parent_idx
    ON football_brief.assets (parent_asset_id)
    WHERE parent_asset_id IS NOT NULL;

CREATE TRIGGER assets_touch_updated_at
BEFORE UPDATE ON football_brief.assets
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.rights_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    evidence_type text NOT NULL CHECK (evidence_type IN (
        'license', 'receipt', 'contract', 'consent', 'source_snapshot',
        'terms_snapshot', 'attribution_record', 'other'
    )),
    storage_uri text NOT NULL,
    sha256 char(64) NOT NULL,
    source_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (asset_id, sha256)
);

CREATE INDEX rights_evidence_asset_idx
    ON football_brief.rights_evidence (asset_id);

CREATE TABLE football_brief.asset_rights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    supersedes_rights_id uuid REFERENCES football_brief.asset_rights(id) ON DELETE RESTRICT,
    rights_basis text NOT NULL DEFAULT 'unknown' CHECK (rights_basis IN (
        'owned', 'commissioned', 'licensed', 'stock', 'creative_commons',
        'public_domain', 'ai_generated', 'client_supplied', 'unknown'
    )),
    asset_owner text,
    licensor text,
    license_type text,
    license_version text,
    license_url text,
    terms_snapshot_uri text,
    terms_snapshot_hash char(64),
    commercial_use_allowed boolean NOT NULL DEFAULT false,
    editorial_use_allowed boolean NOT NULL DEFAULT false,
    modification_allowed boolean NOT NULL DEFAULT false,
    synthetic_edit_allowed boolean NOT NULL DEFAULT false,
    attribution_required boolean NOT NULL DEFAULT false,
    attribution_text text,
    territories text[] NOT NULL DEFAULT ARRAY['worldwide']::text[],
    platforms text[] NOT NULL DEFAULT ARRAY[]::text[],
    campaigns text[] NOT NULL DEFAULT ARRAY[]::text[],
    valid_from timestamptz,
    expires_at timestamptz,
    review_due_at timestamptz,
    approval_status text NOT NULL DEFAULT 'pending' CHECK (approval_status IN (
        'pending', 'approved', 'rejected', 'expired', 'revoked'
    )),
    approved_by text,
    approved_at timestamptz,
    rejection_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT rights_expiry_after_start CHECK (
        expires_at IS NULL OR valid_from IS NULL OR expires_at > valid_from
    ),
    CONSTRAINT rights_attribution_present CHECK (
        attribution_required = false OR nullif(btrim(attribution_text), '') IS NOT NULL
    ),
    CONSTRAINT approved_rights_have_approver CHECK (
        approval_status <> 'approved' OR (
            approved_by IS NOT NULL AND approved_at IS NOT NULL
        )
    )
);

CREATE INDEX asset_rights_asset_status_idx
    ON football_brief.asset_rights (asset_id, approval_status);
CREATE INDEX asset_rights_expiry_idx
    ON football_brief.asset_rights (expires_at)
    WHERE approval_status = 'approved' AND expires_at IS NOT NULL;

CREATE TRIGGER asset_rights_touch_updated_at
BEFORE UPDATE ON football_brief.asset_rights
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.approved_voices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    provider_voice_id text NOT NULL,
    display_name text NOT NULL,
    voice_type text NOT NULL CHECK (voice_type IN (
        'premade', 'licensed_synthetic', 'human_recorded', 'cloned'
    )),
    approval_status text NOT NULL DEFAULT 'pending' CHECK (approval_status IN (
        'pending', 'approved', 'rejected', 'revoked', 'expired'
    )),
    consent_evidence_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    allowed_languages text[] NOT NULL DEFAULT ARRAY['en']::text[],
    allowed_platforms text[] NOT NULL DEFAULT ARRAY[]::text[],
    prohibited_uses text[] NOT NULL DEFAULT ARRAY[]::text[],
    expires_at timestamptz,
    approved_by text,
    approved_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_voice_id),
    CONSTRAINT approved_voice_has_approver CHECK (
        approval_status <> 'approved' OR (
            approved_by IS NOT NULL AND approved_at IS NOT NULL
        )
    ),
    CONSTRAINT cloned_voice_requires_consent CHECK (
        NOT (
            voice_type = 'cloned'
            AND approval_status = 'approved'
            AND consent_evidence_asset_id IS NULL
        )
    )
);

CREATE TRIGGER approved_voices_touch_updated_at
BEFORE UPDATE ON football_brief.approved_voices
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

COMMENT ON TABLE football_brief.assets IS
    'Canonical registry for every source, generated, derived, and output asset.';
COMMENT ON TABLE football_brief.asset_rights IS
    'Versioned rights assertions. Renderer authorization must also verify evidence, platform, territory, expiry, and requested use.';
COMMENT ON TABLE football_brief.approved_voices IS
    'Voice allowlist. Cloned voices cannot be approved without consent evidence.';

COMMIT;
