-- Football Brief Phase 0: approved voice, music, and font policy enforcement
-- Depends on migrations/0001 through 0009

BEGIN;

ALTER TABLE football_brief.approved_voices
    ADD COLUMN preview_only boolean NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION football_brief.validate_approved_voice_policy()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    consent_asset football_brief.assets%ROWTYPE;
BEGIN
    IF NEW.approval_status = 'approved'
       AND NEW.voice_type = 'cloned' THEN
        IF NEW.consent_evidence_asset_id IS NULL THEN
            RAISE EXCEPTION 'Approved cloned voices require consent evidence';
        END IF;

        SELECT * INTO consent_asset
        FROM football_brief.assets
        WHERE id = NEW.consent_evidence_asset_id;

        IF consent_asset.id IS NULL
           OR consent_asset.asset_type <> 'license_evidence'
           OR consent_asset.lifecycle_status NOT IN ('internal_only', 'approved')
           OR consent_asset.metadata->>'evidence_type' IS DISTINCT FROM 'consent' THEN
            RAISE EXCEPTION 'Cloned voice consent must reference canonical consent evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER approved_voices_policy_guard
BEFORE INSERT OR UPDATE ON football_brief.approved_voices
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_approved_voice_policy();

CREATE INDEX approved_voices_lookup_policy_idx
    ON football_brief.approved_voices (
        provider,
        provider_voice_id,
        approval_status,
        preview_only
    );

CREATE TABLE football_brief.narration_outputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL
        REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    render_manifest_id uuid
        REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    stage_execution_id uuid
        REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    mode text NOT NULL CHECK (mode IN ('preview', 'publish')),
    platform text NOT NULL,
    language text NOT NULL,
    text_hash char(64) NOT NULL,
    text_length integer NOT NULL CHECK (text_length >= 0),
    approved_voice_id uuid
        REFERENCES football_brief.approved_voices(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    provider_voice_id text NOT NULL,
    provider_request_id text NOT NULL,
    model_id text NOT NULL,
    output_asset_id uuid
        REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    output_sha256 char(64),
    created_by text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT publish_narration_requires_approval_and_output CHECK (
        mode <> 'publish'
        OR (approved_voice_id IS NOT NULL AND output_asset_id IS NOT NULL AND output_sha256 IS NOT NULL)
    )
);

CREATE UNIQUE INDEX narration_outputs_provider_request_idx
    ON football_brief.narration_outputs (provider, provider_request_id);
CREATE INDEX narration_outputs_workflow_idx
    ON football_brief.narration_outputs (workflow_run_id, created_at DESC);
CREATE INDEX narration_outputs_manifest_idx
    ON football_brief.narration_outputs (render_manifest_id, created_at DESC)
    WHERE render_manifest_id IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.validate_narration_output_policy()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    voice football_brief.approved_voices%ROWTYPE;
    output_asset football_brief.assets%ROWTYPE;
BEGIN
    IF NEW.approved_voice_id IS NOT NULL THEN
        SELECT * INTO voice
        FROM football_brief.approved_voices
        WHERE id = NEW.approved_voice_id;

        IF voice.id IS NULL THEN
            RAISE EXCEPTION 'Narration voice approval not found';
        END IF;

        IF voice.provider IS DISTINCT FROM NEW.provider
           OR voice.provider_voice_id IS DISTINCT FROM NEW.provider_voice_id THEN
            RAISE EXCEPTION 'Narration provider voice does not match approval';
        END IF;

        IF NEW.mode = 'publish' THEN
            IF voice.approval_status <> 'approved'
               OR voice.preview_only
               OR (voice.expires_at IS NOT NULL AND voice.expires_at <= now()) THEN
                RAISE EXCEPTION 'Publish narration voice is not currently approved';
            END IF;
        END IF;
    ELSIF NEW.mode = 'publish' THEN
        RAISE EXCEPTION 'Publish narration requires approved voice';
    END IF;

    IF NEW.output_asset_id IS NOT NULL THEN
        SELECT * INTO output_asset
        FROM football_brief.assets
        WHERE id = NEW.output_asset_id;

        IF output_asset.id IS NULL
           OR output_asset.asset_type <> 'voice'
           OR output_asset.sha256 IS DISTINCT FROM NEW.output_sha256 THEN
            RAISE EXCEPTION 'Narration output asset hash/type mismatch';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER narration_outputs_policy_guard
BEFORE INSERT ON football_brief.narration_outputs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_narration_output_policy();

COMMENT ON TABLE football_brief.narration_outputs IS
    'Immutable audit records for generated narration: text hash, approved voice, provider request/model, and output asset hash.';
COMMENT ON COLUMN football_brief.approved_voices.preview_only IS
    'Development voices may be explicitly allowed for preview runs, but never for publish narration.';

COMMIT;
