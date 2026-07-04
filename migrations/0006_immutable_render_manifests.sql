-- Football Brief Phase 0: immutable preview and publish render manifests
-- Depends on migrations/0001 through 0005

BEGIN;

ALTER TABLE football_brief.render_manifests
    DROP CONSTRAINT publish_manifest_requires_approval,
    ADD COLUMN parent_manifest_id uuid
        REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    ADD COLUMN schema_version text NOT NULL DEFAULT '1.0.0',
    ADD COLUMN status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'sealed', 'approved')),
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
SET status = CASE
        WHEN mode = 'preview' THEN 'sealed'
        ELSE 'approved'
    END,
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
    output_metadata = jsonb_build_object(
        'NOT_FOR_PUBLICATION', mode = 'preview'
    );

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
            status IN ('draft', 'sealed')
            AND not_for_publication = true
            AND watermark_text IS NOT NULL
            AND length(trim(watermark_text)) > 0
        )
    ),
    ADD CONSTRAINT publish_manifest_metadata CHECK (
        mode <> 'publish' OR (
            status IN ('draft', 'approved')
            AND not_for_publication = false
            AND watermark_text IS NULL
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

CREATE OR REPLACE FUNCTION football_brief.enforce_manifest_sealing()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Render manifests are append-only';
    END IF;

    IF OLD.status = 'draft'
       AND NEW.status IN ('sealed', 'approved')
       AND (to_jsonb(NEW) - ARRAY[
            'status', 'approved_by', 'approved_at', 'approval_review_id'
       ]) = (to_jsonb(OLD) - ARRAY[
            'status', 'approved_by', 'approved_at', 'approval_review_id'
       ]) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Sealed or approved render manifests are immutable';
END;
$$;

CREATE TRIGGER render_manifests_immutable
BEFORE UPDATE OR DELETE ON football_brief.render_manifests
FOR EACH ROW EXECUTE FUNCTION football_brief.enforce_manifest_sealing();

CREATE OR REPLACE FUNCTION football_brief.reject_manifest_asset_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Render manifest assets are append-only';
    RETURN NULL;
END;
$$;

CREATE TRIGGER render_manifest_assets_immutable
BEFORE UPDATE OR DELETE ON football_brief.render_manifest_assets
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_manifest_asset_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_manifest_asset_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM football_brief.render_manifests
        WHERE id = NEW.render_manifest_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION 'Assets can only be added while a manifest is draft';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER render_manifest_assets_insert_guard
BEFORE INSERT ON football_brief.render_manifest_assets
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_manifest_asset_insert();

CREATE OR REPLACE FUNCTION football_brief.validate_manifest_final_state()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    review_decision text;
    review_workflow_id uuid;
    gate_outcome text;
    gate_workflow_id uuid;
BEGIN
    IF NEW.status = 'draft' THEN
        RAISE EXCEPTION 'Render manifest must be sealed before commit';
    END IF;

    IF NEW.mode = 'preview' THEN
        IF NEW.status <> 'sealed' OR NOT NEW.not_for_publication THEN
            RAISE EXCEPTION 'Preview manifest must be sealed and non-publishable';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status <> 'approved'
       OR NEW.approved_by IS NULL
       OR NEW.approved_at IS NULL
       OR NEW.approval_review_id IS NULL
       OR NEW.rights_gate_evaluation_id IS NULL THEN
        RAISE EXCEPTION 'Publish manifest requires approval and a passing rights evaluation';
    END IF;

    SELECT decision, workflow_run_id
      INTO review_decision, review_workflow_id
    FROM football_brief.human_reviews
    WHERE id = NEW.approval_review_id;

    IF review_decision <> 'approved' OR review_workflow_id <> NEW.workflow_run_id THEN
        RAISE EXCEPTION 'Publish manifest approval review is invalid';
    END IF;

    SELECT outcome, workflow_run_id
      INTO gate_outcome, gate_workflow_id
    FROM football_brief.rights_gate_evaluations
    WHERE id = NEW.rights_gate_evaluation_id;

    IF gate_outcome <> 'pass' OR gate_workflow_id <> NEW.workflow_run_id THEN
        RAISE EXCEPTION 'Publish manifest rights evaluation is invalid';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM football_brief.render_manifest_assets
        WHERE render_manifest_id = NEW.id
    ) THEN
        RAISE EXCEPTION 'Publish manifest requires at least one asset';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM football_brief.render_manifest_assets AS manifest_asset
        JOIN football_brief.assets AS asset ON asset.id = manifest_asset.asset_id
        WHERE manifest_asset.render_manifest_id = NEW.id
          AND (
              manifest_asset.asset_rights_id IS NULL
              OR manifest_asset.asset_sha256 <> asset.sha256
          )
    ) THEN
        RAISE EXCEPTION 'Publish manifest assets require rights and matching hashes';
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER render_manifest_final_state
AFTER INSERT OR UPDATE ON football_brief.render_manifests
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_manifest_final_state();

CREATE OR REPLACE FUNCTION football_brief.derive_render_job_mode()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    SELECT mode, (mode = 'preview'), watermark_text, output_metadata
      INTO NEW.mode, NEW.not_for_publication, NEW.watermark_text, NEW.output_metadata
    FROM football_brief.render_manifests
    WHERE id = NEW.render_manifest_id AND status IN ('sealed', 'approved');

    IF NEW.mode IS NULL THEN
        RAISE EXCEPTION 'Render job requires a sealed or approved manifest';
    END IF;
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
