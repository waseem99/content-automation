-- Football Brief Phase 0: validate publish manifest approval and assets
-- Depends on migrations/0007_manifest_deferred_validation_fix.sql

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.validate_publish_manifest(manifest_id uuid)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    current_manifest football_brief.render_manifests%ROWTYPE;
    review_decision text;
    review_workflow_id uuid;
    gate_outcome text;
    gate_workflow_id uuid;
BEGIN
    SELECT * INTO current_manifest
    FROM football_brief.render_manifests
    WHERE id = manifest_id;

    IF current_manifest.status <> 'approved'
       OR current_manifest.approved_by IS NULL
       OR current_manifest.approved_at IS NULL
       OR current_manifest.approval_review_id IS NULL
       OR current_manifest.rights_gate_evaluation_id IS NULL THEN
        RAISE EXCEPTION 'Publish manifest requires approval and a passing rights evaluation';
    END IF;

    SELECT decision, workflow_run_id
      INTO review_decision, review_workflow_id
    FROM football_brief.human_reviews
    WHERE id = current_manifest.approval_review_id;

    IF review_decision IS DISTINCT FROM 'approved'
       OR review_workflow_id IS DISTINCT FROM current_manifest.workflow_run_id THEN
        RAISE EXCEPTION 'Publish manifest approval review is invalid';
    END IF;

    SELECT outcome, workflow_run_id
      INTO gate_outcome, gate_workflow_id
    FROM football_brief.rights_gate_evaluations
    WHERE id = current_manifest.rights_gate_evaluation_id;

    IF gate_outcome IS DISTINCT FROM 'pass'
       OR gate_workflow_id IS DISTINCT FROM current_manifest.workflow_run_id THEN
        RAISE EXCEPTION 'Publish manifest rights evaluation is invalid';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM football_brief.render_manifest_assets
        WHERE render_manifest_id = current_manifest.id
    ) THEN
        RAISE EXCEPTION 'Publish manifest requires at least one asset';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM football_brief.render_manifest_assets AS manifest_asset
        JOIN football_brief.assets AS asset ON asset.id = manifest_asset.asset_id
        WHERE manifest_asset.render_manifest_id = current_manifest.id
          AND (
              manifest_asset.asset_rights_id IS NULL
              OR manifest_asset.asset_sha256 <> asset.sha256
          )
    ) THEN
        RAISE EXCEPTION 'Publish manifest assets require rights and matching hashes';
    END IF;
END;
$$;

COMMIT;
