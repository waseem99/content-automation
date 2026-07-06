-- Football Brief Phase 0: asset lineage and provider-generation evidence
-- Depends on migrations/0001 through 0010

BEGIN;

CREATE TABLE football_brief.provider_generation_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_call_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.provider_calls(id) ON DELETE RESTRICT,
    output_asset_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    parent_asset_id uuid
        REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    workflow_run_id uuid NOT NULL
        REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid NOT NULL
        REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    operation text NOT NULL,
    model_id text NOT NULL,
    prompt_name text,
    prompt_version text,
    prompt_hash char(64),
    request_fingerprint char(64) NOT NULL,
    response_fingerprint char(64) NOT NULL,
    provider_request_id text NOT NULL,
    input_asset_sha256 char(64),
    output_asset_sha256 char(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, operation, request_fingerprint, input_asset_sha256)
);

CREATE INDEX provider_generation_output_idx
    ON football_brief.provider_generation_evidence (output_asset_id);
CREATE INDEX provider_generation_parent_idx
    ON football_brief.provider_generation_evidence (parent_asset_id)
    WHERE parent_asset_id IS NOT NULL;
CREATE INDEX provider_generation_workflow_idx
    ON football_brief.provider_generation_evidence (workflow_run_id, created_at DESC);

CREATE OR REPLACE FUNCTION football_brief.validate_provider_generation_evidence()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    output_asset football_brief.assets%ROWTYPE;
    parent_asset football_brief.assets%ROWTYPE;
    call_row football_brief.provider_calls%ROWTYPE;
    stage_row football_brief.stage_executions%ROWTYPE;
BEGIN
    SELECT * INTO output_asset
    FROM football_brief.assets
    WHERE id = NEW.output_asset_id;

    IF output_asset.id IS NULL THEN
        RAISE EXCEPTION 'Provider generation output asset does not exist';
    END IF;

    IF output_asset.sha256 IS DISTINCT FROM NEW.output_asset_sha256 THEN
        RAISE EXCEPTION 'Provider generation output hash does not match asset';
    END IF;

    IF output_asset.parent_asset_id IS DISTINCT FROM NEW.parent_asset_id THEN
        RAISE EXCEPTION 'Provider generation parent does not match output asset parent';
    END IF;

    IF NEW.parent_asset_id IS NOT NULL THEN
        SELECT * INTO parent_asset
        FROM football_brief.assets
        WHERE id = NEW.parent_asset_id;

        IF parent_asset.id IS NULL THEN
            RAISE EXCEPTION 'Provider generation parent asset does not exist';
        END IF;
        IF parent_asset.sha256 IS DISTINCT FROM NEW.input_asset_sha256 THEN
            RAISE EXCEPTION 'Provider generation input hash does not match parent asset';
        END IF;
    END IF;

    SELECT * INTO call_row
    FROM football_brief.provider_calls
    WHERE id = NEW.provider_call_id;

    IF call_row.id IS NULL
       OR call_row.status <> 'succeeded'
       OR call_row.provider IS DISTINCT FROM NEW.provider
       OR call_row.operation IS DISTINCT FROM NEW.operation
       OR call_row.stage_execution_id IS DISTINCT FROM NEW.stage_execution_id
       OR call_row.request_fingerprint IS DISTINCT FROM NEW.request_fingerprint
       OR call_row.response_fingerprint IS DISTINCT FROM NEW.response_fingerprint
       OR call_row.provider_request_id IS DISTINCT FROM NEW.provider_request_id THEN
        RAISE EXCEPTION 'Provider generation evidence does not match succeeded provider call';
    END IF;

    SELECT * INTO stage_row
    FROM football_brief.stage_executions
    WHERE id = NEW.stage_execution_id;

    IF stage_row.id IS NULL
       OR stage_row.workflow_run_id IS DISTINCT FROM NEW.workflow_run_id THEN
        RAISE EXCEPTION 'Provider generation workflow does not match stage execution';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER provider_generation_evidence_guard
BEFORE INSERT ON football_brief.provider_generation_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_provider_generation_evidence();

CREATE OR REPLACE FUNCTION football_brief.reject_provider_generation_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Provider generation evidence is append-only';
END;
$$;

CREATE TRIGGER provider_generation_evidence_immutable
BEFORE UPDATE OR DELETE ON football_brief.provider_generation_evidence
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_provider_generation_evidence_mutation();

CREATE OR REPLACE FUNCTION football_brief.require_publish_generated_asset_evidence()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    asset_row football_brief.assets%ROWTYPE;
BEGIN
    SELECT * INTO asset_row
    FROM football_brief.assets
    WHERE id = NEW.asset_id;

    IF asset_row.source_type = 'ai_generated'
       AND NOT EXISTS (
           SELECT 1
           FROM football_brief.provider_generation_evidence
           WHERE output_asset_id = NEW.asset_id
       ) THEN
        RAISE EXCEPTION 'Generated assets require provider generation evidence before publish manifest use';
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER publish_manifest_generated_asset_evidence
AFTER INSERT ON football_brief.render_manifest_assets
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION football_brief.require_publish_generated_asset_evidence();

COMMENT ON TABLE football_brief.provider_generation_evidence IS
    'Append-only evidence linking generated or transformed assets to provider calls, prompt/config hashes, parent inputs, and output bytes.';

COMMIT;
