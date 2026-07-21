-- Versioned script, scene, claim, and source evidence.

BEGIN;

CREATE TABLE football_brief.script_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    production_workflow_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    current_version_id uuid NOT NULL,
    lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
    created_by text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE football_brief.script_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_document_id uuid NOT NULL
        REFERENCES football_brief.script_documents(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_version_id uuid,
    basis_content_version integer NOT NULL CHECK (basis_content_version >= 1),
    status text NOT NULL DEFAULT 'working' CHECK (status IN (
        'working', 'in_review', 'approved', 'changes_requested', 'rejected', 'superseded'
    )),
    platform text NOT NULL,
    format text NOT NULL,
    language text NOT NULL,
    target_duration_seconds numeric(10,3) NOT NULL CHECK (target_duration_seconds > 0),
    words_per_minute numeric(8,3) NOT NULL DEFAULT 150 CHECK (words_per_minute BETWEEN 60 AND 260),
    word_count integer NOT NULL DEFAULT 0 CHECK (word_count >= 0),
    estimated_duration_seconds numeric(10,3) NOT NULL DEFAULT 0 CHECK (estimated_duration_seconds >= 0),
    duration_tolerance_percent numeric(6,3) NOT NULL DEFAULT 10 CHECK (
        duration_tolerance_percent BETWEEN 0 AND 30
    ),
    hook_text text NOT NULL DEFAULT '',
    cta_text text NOT NULL DEFAULT '',
    full_text text NOT NULL DEFAULT '',
    content_fingerprint char(64),
    adapter_mode text NOT NULL DEFAULT 'deterministic' CHECK (adapter_mode IN (
        'deterministic', 'local_model', 'manual'
    )),
    local_model_id text,
    revision_reason text,
    created_by text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    decided_at timestamptz,
    UNIQUE (script_document_id, version),
    UNIQUE (id, script_document_id),
    CHECK (version = 1 OR parent_version_id IS NOT NULL),
    CHECK (version <> 1 OR parent_version_id IS NULL),
    CHECK (status = 'working' OR submitted_at IS NOT NULL),
    CHECK (status NOT IN ('approved', 'changes_requested', 'rejected') OR decided_at IS NOT NULL),
    CHECK (status = 'working' OR content_fingerprint IS NOT NULL)
);

ALTER TABLE football_brief.script_versions
    ADD CONSTRAINT script_version_parent_fk
    FOREIGN KEY (parent_version_id, script_document_id)
    REFERENCES football_brief.script_versions(id, script_document_id)
    ON DELETE RESTRICT;

ALTER TABLE football_brief.script_documents
    ADD CONSTRAINT script_document_current_version_fk
    FOREIGN KEY (current_version_id, id)
    REFERENCES football_brief.script_versions(id, script_document_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX script_one_live_version_idx
ON football_brief.script_versions (script_document_id)
WHERE status IN ('working', 'in_review');

CREATE INDEX script_versions_history_idx
ON football_brief.script_versions (script_document_id, version DESC);

CREATE TABLE football_brief.script_sections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    sequence integer NOT NULL CHECK (sequence >= 1),
    section_key text NOT NULL CHECK (length(btrim(section_key)) BETWEEN 1 AND 100),
    section_type text NOT NULL CHECK (section_type IN ('hook', 'narration', 'cta')),
    text text NOT NULL CHECK (length(btrim(text)) >= 1),
    target_duration_seconds numeric(10,3) NOT NULL CHECK (target_duration_seconds > 0),
    estimated_duration_seconds numeric(10,3) NOT NULL CHECK (estimated_duration_seconds >= 0),
    word_count integer NOT NULL CHECK (word_count >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (script_version_id, sequence),
    UNIQUE (script_version_id, section_key),
    UNIQUE (id, script_version_id)
);

CREATE TABLE football_brief.script_scene_plan_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    script_section_id uuid NOT NULL,
    sequence integer NOT NULL CHECK (sequence >= 1),
    scene_key text NOT NULL CHECK (length(btrim(scene_key)) BETWEEN 1 AND 100),
    narration_text text NOT NULL CHECK (length(btrim(narration_text)) >= 1),
    visual_brief text NOT NULL CHECK (length(btrim(visual_brief)) >= 10),
    on_screen_text text,
    target_duration_seconds numeric(10,3) NOT NULL CHECK (target_duration_seconds > 0),
    source_requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (script_version_id, sequence),
    UNIQUE (script_version_id, scene_key),
    FOREIGN KEY (script_section_id, script_version_id)
        REFERENCES football_brief.script_sections(id, script_version_id)
        ON DELETE RESTRICT
);

CREATE TABLE football_brief.script_claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    script_section_id uuid NOT NULL,
    claim_key text NOT NULL CHECK (length(btrim(claim_key)) BETWEEN 1 AND 100),
    claim_text text NOT NULL CHECK (length(btrim(claim_text)) >= 3),
    claim_type text NOT NULL CHECK (claim_type IN ('factual', 'inference', 'opinion', 'uncertain')),
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sensitivity text NOT NULL DEFAULT 'low' CHECK (sensitivity IN ('low', 'medium', 'high')),
    support_status text NOT NULL DEFAULT 'needs_source' CHECK (support_status IN (
        'supported', 'needs_source', 'unsupported', 'not_applicable'
    )),
    wording_limitations text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (script_version_id, claim_key),
    UNIQUE (id, script_version_id),
    FOREIGN KEY (script_section_id, script_version_id)
        REFERENCES football_brief.script_sections(id, script_version_id)
        ON DELETE RESTRICT,
    CHECK (claim_type <> 'factual' OR support_status <> 'not_applicable')
);

CREATE TABLE football_brief.script_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    source_key text NOT NULL CHECK (length(btrim(source_key)) BETWEEN 1 AND 100),
    source_type text NOT NULL CHECK (source_type IN (
        'primary', 'government', 'academic', 'secondary', 'news', 'expert', 'internal_reference'
    )),
    title text NOT NULL CHECK (length(btrim(title)) >= 3),
    publisher text,
    canonical_url text,
    published_on date,
    accessed_at timestamptz NOT NULL DEFAULT now(),
    quality_score numeric(5,2) NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    rights_declaration text NOT NULL CHECK (rights_declaration IN (
        'owned', 'licensed', 'publicly_accessible', 'quotation_only', 'internal_research'
    )),
    permitted_use text NOT NULL CHECK (length(btrim(permitted_use)) >= 3),
    evidence_digest char(64) NOT NULL,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (script_version_id, source_key),
    UNIQUE (id, script_version_id),
    CHECK (canonical_url IS NULL OR canonical_url !~* '(token|signature|password|secret|cookie)=')
);

CREATE TABLE football_brief.script_claim_sources (
    script_version_id uuid NOT NULL
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    claim_id uuid NOT NULL,
    source_id uuid NOT NULL,
    support_type text NOT NULL CHECK (support_type IN ('direct', 'corroborating', 'contextual', 'limitation')),
    locator text,
    support_note text NOT NULL CHECK (length(btrim(support_note)) >= 3),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, source_id, support_type),
    FOREIGN KEY (claim_id, script_version_id)
        REFERENCES football_brief.script_claims(id, script_version_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id, script_version_id)
        REFERENCES football_brief.script_sources(id, script_version_id) ON DELETE RESTRICT
);

CREATE TRIGGER script_documents_touch_updated_at
BEFORE UPDATE ON football_brief.script_documents
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TRIGGER script_versions_touch_updated_at
BEFORE UPDATE ON football_brief.script_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TRIGGER script_sections_touch_updated_at
BEFORE UPDATE ON football_brief.script_sections
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TRIGGER script_scene_plan_touch_updated_at
BEFORE UPDATE ON football_brief.script_scene_plan_entries
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TRIGGER script_claims_touch_updated_at
BEFORE UPDATE ON football_brief.script_claims
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

COMMENT ON TABLE football_brief.script_versions IS
    'Exact script versions. Approved versions are immutable and downstream jobs pin the version ID.';
COMMENT ON TABLE football_brief.script_claims IS
    'Claim register with confidence, sensitivity, wording limits, and factual support state.';
COMMENT ON TABLE football_brief.script_sources IS
    'Source pack metadata and rights declarations; raw confidential source content is not stored.';

COMMIT;
