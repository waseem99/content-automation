-- Football Brief Phase 0: make every rights-evidence file a canonical asset
-- Depends on migrations/0001_phase0_asset_rights.sql

BEGIN;

ALTER TABLE football_brief.rights_evidence
    ADD COLUMN evidence_asset_id uuid;

-- Backfill any pre-existing evidence rows by registering their stored bytes as
-- canonical evidence assets. The existing rights-evidence SHA-256 remains the
-- identity source for this one-time migration only; all new registrations hash
-- the bytes in the application service before insertion.
INSERT INTO football_brief.assets (
    asset_type,
    source_type,
    lifecycle_status,
    storage_uri,
    sha256,
    metadata,
    created_by
)
SELECT DISTINCT
    'license_evidence',
    'unknown',
    'internal_only',
    evidence.storage_uri,
    evidence.sha256,
    jsonb_build_object(
        'backfilled_from', 'rights_evidence',
        'migration', '0003_canonical_rights_evidence.sql'
    ),
    evidence.uploaded_by
FROM football_brief.rights_evidence AS evidence
ON CONFLICT (sha256) DO NOTHING;

UPDATE football_brief.rights_evidence AS evidence
SET evidence_asset_id = asset.id
FROM football_brief.assets AS asset
WHERE asset.sha256 = evidence.sha256
  AND evidence.evidence_asset_id IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM football_brief.rights_evidence
        WHERE evidence_asset_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Unable to canonicalize one or more rights-evidence records';
    END IF;
END;
$$;

ALTER TABLE football_brief.rights_evidence
    ALTER COLUMN evidence_asset_id SET NOT NULL,
    ADD CONSTRAINT rights_evidence_canonical_asset_fk
        FOREIGN KEY (evidence_asset_id)
        REFERENCES football_brief.assets(id)
        ON DELETE RESTRICT,
    ADD CONSTRAINT rights_evidence_target_not_evidence
        CHECK (asset_id <> evidence_asset_id);

CREATE INDEX rights_evidence_evidence_asset_idx
    ON football_brief.rights_evidence (evidence_asset_id);

CREATE UNIQUE INDEX rights_evidence_unique_link_idx
    ON football_brief.rights_evidence (
        asset_id,
        evidence_asset_id,
        evidence_type
    );

COMMENT ON COLUMN football_brief.rights_evidence.evidence_asset_id IS
    'Canonical license_evidence asset containing the evidence bytes.';

COMMIT;
