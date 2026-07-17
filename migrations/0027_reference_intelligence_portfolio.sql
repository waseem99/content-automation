-- P75 reference-intelligence metadata bridge for the portfolio operator surface.
-- Source media and heavy processing remain in the operator-controlled local workspace.

BEGIN;

CREATE TABLE football_brief.reference_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    local_reference_id text NOT NULL UNIQUE,
    source_locator_hash char(64) NOT NULL,
    canonical_url text,
    title text NOT NULL,
    platform text NOT NULL CHECK (platform IN (
        'facebook', 'instagram', 'youtube', 'tiktok', 'x', 'snapchat',
        'google-drive', 'local', 'unknown'
    )),
    media_type text NOT NULL DEFAULT 'unknown' CHECK (media_type IN (
        'video', 'image', 'carousel', 'mixed', 'unknown'
    )),
    rights_declaration text NOT NULL CHECK (rights_declaration IN (
        'owned', 'permitted', 'public-internal-research', 'rights-holder-upload'
    )),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'acquiring', 'processing', 'partial', 'ready_for_review',
        'blocked', 'failed', 'archived'
    )),
    local_processing_required boolean NOT NULL DEFAULT true,
    source_media_synced boolean NOT NULL DEFAULT false,
    automatic_publication_allowed boolean NOT NULL DEFAULT false,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_media_synced = false),
    CHECK (automatic_publication_allowed = false),
    CHECK (canonical_url IS NULL OR canonical_url !~* '(token|signature|password|secret)=')
);

CREATE INDEX reference_sources_queue_idx
    ON football_brief.reference_sources (status, platform, updated_at DESC);
CREATE TRIGGER reference_sources_touch_updated_at BEFORE UPDATE
    ON football_brief.reference_sources
    FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.reference_ingestion_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_source_id uuid NOT NULL
        REFERENCES football_brief.reference_sources(id) ON DELETE RESTRICT,
    attempt integer NOT NULL CHECK (attempt >= 1),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'partial', 'succeeded', 'failed', 'cancelled'
    )),
    stage text NOT NULL DEFAULT 'intake' CHECK (stage IN (
        'intake', 'acquisition', 'normalization', 'frames', 'transcript',
        'analysis', 'temporal_report', 'fingerprint', 'comparison', 'complete'
    )),
    progress_percent integer NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    worker_mode text NOT NULL DEFAULT 'local' CHECK (worker_mode = 'local'),
    worker_label text,
    error_code text,
    sanitized_error text,
    fallback_action text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reference_source_id, attempt),
    CHECK (sanitized_error IS NULL OR sanitized_error !~* '(password|secret|token|cookie)[=:]'),
    CHECK (status NOT IN ('succeeded', 'failed', 'cancelled') OR finished_at IS NOT NULL)
);

CREATE INDEX reference_jobs_queue_idx
    ON football_brief.reference_ingestion_jobs (status, created_at);
CREATE TRIGGER reference_jobs_touch_updated_at BEFORE UPDATE
    ON football_brief.reference_ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.reference_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_source_id uuid NOT NULL
        REFERENCES football_brief.reference_sources(id) ON DELETE RESTRICT,
    ingestion_job_id uuid
        REFERENCES football_brief.reference_ingestion_jobs(id) ON DELETE RESTRICT,
    artifact_kind text NOT NULL CHECK (artifact_kind IN (
        'contact_sheet', 'analysis_report', 'temporal_report', 'fingerprint',
        'comparison_report', 'pattern_library', 'pattern_brief', 'originality_gate'
    )),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    local_locator text NOT NULL,
    sha256 char(64) NOT NULL,
    mime_type text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    contains_source_media boolean NOT NULL DEFAULT false,
    review_safe boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reference_source_id, artifact_kind, version),
    CHECK (contains_source_media = false),
    CHECK (local_locator ~ '^reference://[A-Za-z0-9._/-]+$')
);

CREATE INDEX reference_artifacts_source_idx
    ON football_brief.reference_artifacts (reference_source_id, artifact_kind);

CREATE TABLE football_brief.reference_brand_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_source_id uuid NOT NULL
        REFERENCES football_brief.reference_sources(id) ON DELETE RESTRICT,
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    active boolean NOT NULL DEFAULT true,
    assigned_by text NOT NULL,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX reference_brand_assignment_active_idx
    ON football_brief.reference_brand_assignments (reference_source_id, brand_id)
    WHERE active = true;

CREATE TABLE football_brief.reference_approval_gates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_source_id uuid NOT NULL
        REFERENCES football_brief.reference_sources(id) ON DELETE RESTRICT,
    gate text NOT NULL CHECK (gate IN ('rights', 'originality', 'editorial')),
    decision text NOT NULL CHECK (decision IN (
        'pending', 'approved', 'changes_requested', 'rejected'
    )),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    reviewer text NOT NULL,
    rationale text NOT NULL,
    evidence_digest char(64) NOT NULL,
    automatic_decision boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reference_source_id, gate, version, reviewer),
    CHECK (automatic_decision = false)
);

CREATE INDEX reference_gates_source_idx
    ON football_brief.reference_approval_gates (reference_source_id, gate, created_at DESC);

CREATE TABLE football_brief.research_idea_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_source_id uuid NOT NULL
        REFERENCES football_brief.reference_sources(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    relationship text NOT NULL CHECK (relationship IN (
        'pattern_evidence', 'topic_signal', 'format_evidence', 'risk_reference'
    )),
    pattern_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    transformation_note text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reference_source_id, portfolio_content_id, relationship),
    CHECK (length(btrim(transformation_note)) >= 20)
);

COMMENT ON TABLE football_brief.reference_sources IS
    'Review-safe metadata only. Source media remains local and never enters PostgreSQL or Vercel.';
COMMENT ON TABLE football_brief.reference_ingestion_jobs IS
    'Local-worker progress records. The portfolio API never performs heavy media processing.';
COMMENT ON TABLE football_brief.reference_artifacts IS
    'Metadata pointers to review-safe local outputs; source media artifacts are prohibited.';
COMMENT ON TABLE football_brief.reference_approval_gates IS
    'Append-only human rights, originality, and editorial decisions; no automatic approval.';
COMMENT ON TABLE football_brief.research_idea_links IS
    'Traceability from abstract research mechanics to original ideas; never a source-asset link.';

COMMIT;
