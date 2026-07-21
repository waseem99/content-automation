-- Versioned local narration, paragraph takes, mix metadata, and exact script/preset lineage.
-- Audio bytes remain in the canonical asset store; PostgreSQL retains metadata and evidence only.

BEGIN;

CREATE TABLE football_brief.audio_productions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version >= 1),
    script_version_id uuid NOT NULL REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    brand_profile_id uuid NOT NULL REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    narration_preset_id uuid NOT NULL REFERENCES football_brief.brand_narration_presets(id) ON DELETE RESTRICT,
    approved_voice_id uuid NOT NULL REFERENCES football_brief.approved_voices(id) ON DELETE RESTRICT,
    provider text NOT NULL,
    provider_voice_id text NOT NULL,
    model_id text NOT NULL,
    preset_snapshot jsonb NOT NULL,
    pronunciation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'in_review', 'approved', 'changes_requested', 'rejected', 'superseded'
    )),
    current_mix_version_id uuid,
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version >= 1),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    decided_at timestamptz,
    UNIQUE (portfolio_content_id, script_version_id),
    UNIQUE (id, portfolio_content_id),
    CONSTRAINT audio_production_review_timestamp CHECK (
        status = 'working' OR submitted_at IS NOT NULL
    ),
    CONSTRAINT audio_production_decision_timestamp CHECK (
        status NOT IN ('approved', 'changes_requested', 'rejected') OR decided_at IS NOT NULL
    )
);

CREATE INDEX audio_productions_content_idx
ON football_brief.audio_productions (portfolio_content_id, created_at DESC);

CREATE UNIQUE INDEX audio_productions_one_live_idx
ON football_brief.audio_productions (portfolio_content_id)
WHERE status IN ('working', 'in_review', 'approved');

CREATE TRIGGER audio_productions_touch_updated_at
BEFORE UPDATE ON football_brief.audio_productions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.audio_pronunciation_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    token text NOT NULL CHECK (length(btrim(token)) BETWEEN 1 AND 200),
    pronunciation text NOT NULL CHECK (length(btrim(pronunciation)) BETWEEN 1 AND 500),
    locale text NOT NULL DEFAULT 'en-US',
    reason text,
    active boolean NOT NULL DEFAULT true,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (audio_production_id, token, locale, active)
);

CREATE TABLE football_brief.audio_paragraphs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    script_section_id uuid NOT NULL REFERENCES football_brief.script_sections(id) ON DELETE RESTRICT,
    sequence integer NOT NULL CHECK (sequence >= 1),
    paragraph_index integer NOT NULL CHECK (paragraph_index >= 1),
    source_text text NOT NULL CHECK (length(btrim(source_text)) BETWEEN 1 AND 10000),
    text_fingerprint char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (audio_production_id, sequence),
    UNIQUE (audio_production_id, script_section_id, paragraph_index),
    UNIQUE (id, audio_production_id)
);

CREATE INDEX audio_paragraphs_production_idx
ON football_brief.audio_paragraphs (audio_production_id, sequence);

CREATE TABLE football_brief.audio_segment_takes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    paragraph_id uuid NOT NULL REFERENCES football_brief.audio_paragraphs(id) ON DELETE RESTRICT,
    take_version integer NOT NULL CHECK (take_version >= 1),
    generation_job_id uuid REFERENCES football_brief.generation_jobs(id) ON DELETE RESTRICT,
    asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'generated', 'selected', 'failed', 'superseded'
    )),
    provider text NOT NULL,
    model_id text NOT NULL,
    approved_voice_id uuid NOT NULL REFERENCES football_brief.approved_voices(id) ON DELETE RESTRICT,
    narration_preset_id uuid NOT NULL REFERENCES football_brief.brand_narration_presets(id) ON DELETE RESTRICT,
    input_fingerprint char(64) NOT NULL,
    pronunciation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    duration_seconds numeric(12,3) CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    sample_rate_hz integer CHECK (sample_rate_hz IS NULL OR sample_rate_hz BETWEEN 8000 AND 384000),
    channels integer CHECK (channels IS NULL OR channels BETWEEN 1 AND 16),
    integrated_lufs numeric(8,3),
    true_peak_dbfs numeric(8,3),
    clipping_count integer NOT NULL DEFAULT 0 CHECK (clipping_count >= 0),
    silence_ratio numeric(8,5) CHECK (silence_ratio IS NULL OR silence_ratio BETWEEN 0 AND 1),
    qc_status text NOT NULL DEFAULT 'pending' CHECK (qc_status IN ('pending', 'pass', 'fail')),
    qc_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    timing_source text NOT NULL DEFAULT 'none' CHECK (timing_source IN (
        'none', 'forced_alignment', 'proportional_preview'
    )),
    word_timings jsonb NOT NULL DEFAULT '[]'::jsonb,
    actual_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    external_fee_incurred boolean NOT NULL DEFAULT false,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (paragraph_id, take_version),
    UNIQUE (id, paragraph_id),
    CONSTRAINT generated_audio_take_has_artifact CHECK (
        status NOT IN ('generated', 'selected', 'superseded') OR asset_id IS NOT NULL
    )
);

CREATE UNIQUE INDEX audio_segment_one_selected_idx
ON football_brief.audio_segment_takes (paragraph_id)
WHERE status = 'selected';

CREATE INDEX audio_segment_takes_production_idx
ON football_brief.audio_segment_takes (audio_production_id, paragraph_id, take_version DESC);

CREATE TRIGGER audio_segment_takes_touch_updated_at
BEFORE UPDATE ON football_brief.audio_segment_takes
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.audio_mix_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_production_id uuid NOT NULL REFERENCES football_brief.audio_productions(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_mix_version_id uuid REFERENCES football_brief.audio_mix_versions(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'in_review', 'approved', 'changes_requested', 'rejected', 'superseded'
    )),
    narration_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    final_mix_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    target_lufs numeric(8,3) NOT NULL DEFAULT -16.0,
    peak_limit_dbfs numeric(8,3) NOT NULL DEFAULT -1.0,
    measured_lufs numeric(8,3),
    true_peak_dbfs numeric(8,3),
    clipping_count integer NOT NULL DEFAULT 0 CHECK (clipping_count >= 0),
    silence_ratio numeric(8,5) CHECK (silence_ratio IS NULL OR silence_ratio BETWEEN 0 AND 1),
    duration_seconds numeric(12,3) CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    qc_status text NOT NULL DEFAULT 'pending' CHECK (qc_status IN ('pending', 'pass', 'fail')),
    waveform_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    segment_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,
    mix_settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    alignment_source text NOT NULL DEFAULT 'none' CHECK (alignment_source IN (
        'none', 'forced_alignment', 'proportional_preview'
    )),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    decided_at timestamptz,
    UNIQUE (audio_production_id, version),
    UNIQUE (id, audio_production_id)
);

CREATE UNIQUE INDEX audio_mix_one_live_idx
ON football_brief.audio_mix_versions (audio_production_id)
WHERE status IN ('working', 'in_review');

CREATE TRIGGER audio_mix_versions_touch_updated_at
BEFORE UPDATE ON football_brief.audio_mix_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

ALTER TABLE football_brief.audio_productions
    ADD CONSTRAINT audio_production_current_mix_fk
    FOREIGN KEY (current_mix_version_id, id)
    REFERENCES football_brief.audio_mix_versions(id, audio_production_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE football_brief.audio_mix_tracks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_mix_version_id uuid NOT NULL REFERENCES football_brief.audio_mix_versions(id) ON DELETE RESTRICT,
    track_role text NOT NULL CHECK (track_role IN ('narration', 'music', 'sfx')),
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    asset_rights_id uuid REFERENCES football_brief.asset_rights(id) ON DELETE RESTRICT,
    level_db numeric(8,3) NOT NULL DEFAULT 0,
    ducking_db numeric(8,3) NOT NULL DEFAULT 0,
    start_seconds numeric(12,3) NOT NULL DEFAULT 0 CHECK (start_seconds >= 0),
    end_seconds numeric(12,3) CHECK (end_seconds IS NULL OR end_seconds > start_seconds),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT licensed_track_requires_rights CHECK (
        track_role = 'narration' OR asset_rights_id IS NOT NULL
    )
);

CREATE INDEX audio_mix_tracks_mix_idx
ON football_brief.audio_mix_tracks (audio_mix_version_id, track_role);

COMMENT ON TABLE football_brief.audio_productions IS
    'Exact approved script, brand preset, voice, provider, and model lineage for local narration work.';
COMMENT ON TABLE football_brief.audio_segment_takes IS
    'Paragraph-level local narration take metadata; audio bytes remain in the canonical asset registry.';
COMMENT ON TABLE football_brief.audio_mix_versions IS
    'Versioned narration and final-mix review evidence with measured loudness, peak, silence, waveform, and alignment provenance.';

COMMIT;