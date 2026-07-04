-- Football Brief Phase 0: immutable preview and publish render manifests
-- Depends on migrations/0001 through 0005

BEGIN;

ALTER TABLE football_brief.render_manifests
    ADD COLUMN parent_manifest_id uuid
        REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    ADD COLUMN schema_version text NOT NULL DEFAULT '1.0.0',
    ADD COLUMN status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved')),
    ADD COLUMN material_input_hash char(64),
    ADD COLUMN script_hash char(64),
    ADD COLUMN storyboard_hash char(64),
    ADD COLUMN brand_hash char(64),
    ADD COLUMN policy_hash char(64),
    ADD COLUMN rights_gate_evaluation_id uuid
        REFERENCES football_brief.rights_gate_evaluations(id) ON DELETE RESTRICT,
    ADD COLUMN approval_review_id uuid
        REFERENCES football_brief.human_reviews(id) ON DELETE RESTRICT,
    ADD COLUMN not_for_publication boolean NOT NULL DEFAULT true,
    ADD COLUMN watermark_text text,
    ADD COLUMN output_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE football_brief.render_manifests
SET status = CASE WHEN approved_at IS NULL THEN 'draft' ELSE 'approved' END,
    material_input_hash = manifest_hash,
    script_hash = manifest_hash,
    storyboard_hash = manifest_hash,
    brand_hash = manifest_hash,
    policy_hash = manifest_hash,
    not_for_publication = (mode = 'preview'),
    watermark_text = CASE
        WHEN mode = 'preview' THEN 'PREVIEW - NOT FOR PUBLICATION'
        ELSE NULL
    END,
    output_metadata = CASE
        WHEN mode = 'preview' THEN '{"NOT_FOR_PUBLICATION":true}'::jsonb
        ELSE '{"NOT_FOR_PUBLICATION":false}'::jsonb
    END;

ALTER TABLE football_brief.render_manifests
    ALTER COLUMN material_input_hash SET NOT NULL,
    ALTER COLUMN script_hash SET NOT NULL,
    ALTER COLUMN storyboard_hash SET NOT NULL,
    ALTER COLUMN brand_hash SET NOT NULL,
    ALTER COLUMN policy_hash SET NOT NULL,
    ADD CONSTRAINT render_manifest_version_unique
        UNIQUE (workflow_run_id, manifest_version),
    ADD CONSTRAINT render_manifest_parent_not_self
        CHECK (parent_manifest_id IS NULL OR parent_manifest_id <> id),
    ADD CONSTRAINT preview_manifest_is_non_publishable CHECK (
        mode <> 'preview' OR (
            not_for_publication = true
            AND watermark_text IS NOT NULL
            AND length(trim(watermark_text)) > 0
        )
    ),
    ADD CONSTRAINT publish_manifest_is_approved CHECK (
        mode <> 'publish' OR (
            status = 'approved'
            AND not_for_publication = false
            AND approved_by IS NOT NULL
            AND approved_at IS NOT NULL
            AND approval_review_id IS NOT NULL
            AND rights_gate_evaluation_id IS NOT NULL
        )
    );

ALTER TABLE football_brief.render_manifest_assets
    ALTER COLUMN asset_rights_id DROP NOT NULL,
    ADD COLUMN rights_evidence_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE football_brief.render_jobs
    ADD COLUMN mode text NOT NULL DEFAULT 'preview'
        CHECK (mode IN ('preview', 'publish')),
    ADD COLUMN not_for_publication boolean NOT NULL DEFAULT true,
    ADD COLUMN watermark_text text,
    ADD COLUMN output_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE football_brief.publication_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    render_manifest_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    render_job_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.render_jobs(id) ON DELETE RESTRICT,
    package_hash char(64) NOT NULL UNIQUE,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION football_brief.reject_manifest_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Render manifests and manifest assets are append-only';
    RETURN NULL;
END;
$$;

CREATE TRIGGER render_manifests_immutable
BEFORE UPDATE OR DELETE ON football_brief.render_manifests
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_manifest_mutation();

CREATE TRIGGER render_manifest_assets_immutable
BEFORE UPDATE OR DELETE ON football_brief.render_manifest_assets
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_manifest_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_manifest_asset_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM football_brief.render_manifests
        WHERE id = NEW.render_manifest_id AND status = 'approved'
    ) THEN
        RAISE EXCEPTION 'Approved manifest assets cannot be changed';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER render_manifest_assets_insert_guard
BEFORE INSERT ON football_brief.render_manifest_assets
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_manifest_asset_insert();

CREATE OR REPLACE FUNCTION football_brief.derive_render_job_mode()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    manifest_mode text;
    manifest_watermark text;
    manifest_metadata jsonb;
BEGIN
    SELECT mode, watermark_text, output_metadata
      INTO manifest_mode, manifest_watermark, manifest_metadata
    FROM football_brief.render_manifests
    WHERE id = NEW.render_manifest_id;

    NEW.mode := manifest_mode;
    NEW.not_for_publication := (manifest_mode = 'preview');
    NEW.watermark_text := manifest_watermark;
    NEW.output_metadata := manifest_metadata;
    RETURN NEW;
END;
$$;

CREATE TRIGGER render_jobs_derive_manifest_mode
BEFORE INSERT ON football_brief.render_jobs
FOR EACH ROW EXECUTE FUNCTION football_brief.derive_render_job_mode();

CREATE OR REPLACE FUNCTION football_brief.validate_publication_package()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    manifest_mode text;
    manifest_status text;
    manifest_nfp boolean;
    job_mode text;
    job_nfp boolean;
BEGIN
    SELECT mode, status, not_for_publication
      INTO manifest_mode, manifest_status, manifest_nfp
    FROM football_brief.render_manifests
    WHERE id = NEW.render_manifest_id;

    SELECT mode, not_for_publication
      INTO job_mode, job_nfp
    FROM football_brief.render_jobs
    WHERE id = NEW.render_job_id
      AND render_manifest_id = NEW.render_manifest_id;

    IF manifest_mode <> 'publish'
       OR manifest_status <> 'approved'
       OR manifest_nfp
       OR job_mode <> 'publish'
       OR job_nfp THEN
        RAISE EXCEPTION 'Preview or unapproved output cannot enter a publication package';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER publication_packages_publish_only
BEFORE INSERT ON football_brief.publication_packages
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_publication_package();

COMMENT ON TABLE football_brief.publication_packages IS
    'Eligibility reference only; final package assembly and QC remain a later phase.';

COMMIT;
