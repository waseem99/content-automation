-- Football Brief Phase 0: make every rights-evidence file a canonical asset
-- Depends on migrations/0001_phase0_asset_rights.sql

BEGIN;

ALTER TABLE football_brief.rights_evidence
    ADD COLUMN evidence_asset_id uuid;

-- Backfill any pre-existing evidence rows by registering one deterministic
-- canonical asset per SHA-256. The stored SHA-256 is trusted only for this
-- one-time migration; all new registrations hash the bytes in the service.
INSERT INTO football_brief.assets (
    asset_type,
    source_type,
    lifecycle_status,
    storage_uri,
    sha256,
    metadata,
    created_by
)
SELECT DISTINCT ON (evidence.sha256)
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
ORDER BY evidence.sha256, evidence.created_at, evidence.id
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
        ON DELETE RESTRICT;

CREATE INDEX rights_evidence_evidence_asset_idx
    ON football_brief.rights_evidence (evidence_asset_id);

CREATE UNIQUE INDEX rights_evidence_unique_link_idx
    ON football_brief.rights_evidence (
        asset_id,
        evidence_asset_id,
        evidence_type
    );

COMMENT ON COLUMN football_brief.rights_evidence.evidence_asset_id IS
    'Canonical asset containing the evidence bytes.';

COMMIT;
