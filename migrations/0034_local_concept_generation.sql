-- Review-only local concept generation, scoring, balancing, and plan application.
-- Candidate generation never inserts directly into monthly_content_plans or portfolio_content.

BEGIN;

CREATE TABLE football_brief.concept_generation_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    brand_profile_id uuid NOT NULL REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    month_start date NOT NULL CHECK (month_start = date_trunc('month', month_start)::date),
    requested_count integer NOT NULL CHECK (requested_count BETWEEN 1 AND 200),
    requested_format_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_pillar_targets jsonb NOT NULL DEFAULT '{}'::jsonb,
    seed bigint NOT NULL,
    adapter_mode text NOT NULL DEFAULT 'deterministic' CHECK (adapter_mode IN ('local_model', 'deterministic')),
    local_model_id text,
    paid_provider_allowed boolean NOT NULL DEFAULT false CHECK (paid_provider_allowed = false),
    status text NOT NULL DEFAULT 'generating' CHECK (status IN (
        'generating', 'ready_for_review', 'reviewing', 'slate_ready', 'applied', 'cancelled', 'failed'
    )),
    input_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    gap_report jsonb NOT NULL DEFAULT '{}'::jsonb,
    candidate_count integer NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    duplicate_count integer NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    shortlisted_count integer NOT NULL DEFAULT 0 CHECK (shortlisted_count >= 0),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CONSTRAINT concept_batch_completed_timestamp CHECK (
        status IN ('generating', 'reviewing') OR completed_at IS NOT NULL
    ),
    CONSTRAINT concept_batch_local_model_name CHECK (
        adapter_mode <> 'local_model' OR nullif(btrim(local_model_id), '') IS NOT NULL
    )
);

CREATE INDEX concept_generation_batches_brand_month_idx
ON football_brief.concept_generation_batches (brand_id, month_start, created_at DESC);

CREATE TRIGGER concept_generation_batches_touch_updated_at
BEFORE UPDATE ON football_brief.concept_generation_batches
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.concept_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES football_brief.concept_generation_batches(id) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal >= 1),
    revised_from_candidate_id uuid REFERENCES football_brief.concept_candidates(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'candidate' CHECK (status IN (
        'candidate', 'shortlisted', 'rejected', 'accepted', 'superseded', 'duplicate_blocked'
    )),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 240),
    hook text NOT NULL CHECK (length(btrim(hook)) BETWEEN 3 AND 500),
    concept text NOT NULL CHECK (length(btrim(concept)) BETWEEN 20 AND 5000),
    format text NOT NULL CHECK (length(btrim(format)) BETWEEN 2 AND 80),
    pillar text NOT NULL CHECK (length(btrim(pillar)) BETWEEN 2 AND 120),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 20 AND 5000),
    source_requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
    required_research jsonb NOT NULL DEFAULT '[]'::jsonb,
    factual_risk text NOT NULL CHECK (factual_risk IN ('low', 'medium', 'high')),
    production_complexity text NOT NULL CHECK (production_complexity IN ('low', 'medium', 'high')),
    estimated_cost_usd numeric(12,4) NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    recommended_route text NOT NULL CHECK (recommended_route IN ('local', 'hybrid', 'managed')),
    concept_fingerprint char(64) NOT NULL,
    semantic_key text NOT NULL,
    semantic_tokens text[] NOT NULL DEFAULT ARRAY[]::text[],
    duplicate_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    duplicate_candidate_id uuid REFERENCES football_brief.concept_candidates(id) ON DELETE RESTRICT,
    duplicate_kind text CHECK (duplicate_kind IS NULL OR duplicate_kind IN ('exact', 'semantic')),
    duplicate_similarity numeric(7,6) CHECK (
        duplicate_similarity IS NULL OR duplicate_similarity BETWEEN 0 AND 1
    ),
    originality_score numeric(6,3) NOT NULL CHECK (originality_score BETWEEN 0 AND 100),
    engagement_score numeric(6,3) NOT NULL CHECK (engagement_score BETWEEN 0 AND 100),
    monetization_fit_score numeric(6,3) NOT NULL CHECK (monetization_fit_score BETWEEN 0 AND 100),
    policy_risk_score numeric(6,3) NOT NULL CHECK (policy_risk_score BETWEEN 0 AND 100),
    feasibility_score numeric(6,3) NOT NULL CHECK (feasibility_score BETWEEN 0 AND 100),
    total_score numeric(6,3) NOT NULL CHECK (total_score BETWEEN 0 AND 100),
    score_evidence jsonb NOT NULL,
    generation_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_rationale text,
    reviewed_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    reviewed_at timestamptz,
    accepted_plan_id uuid REFERENCES football_brief.monthly_content_plans(id) ON DELETE RESTRICT,
    accepted_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, ordinal),
    UNIQUE (batch_id, concept_fingerprint),
    CONSTRAINT concept_candidate_duplicate_evidence CHECK (
        status <> 'duplicate_blocked' OR (
            duplicate_kind IS NOT NULL
            AND (duplicate_content_id IS NOT NULL OR duplicate_candidate_id IS NOT NULL)
        )
    ),
    CONSTRAINT concept_candidate_review_evidence CHECK (
        status IN ('candidate', 'duplicate_blocked') OR (
            reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
        )
    ),
    CONSTRAINT concept_candidate_acceptance_pair CHECK (
        (accepted_plan_id IS NULL AND accepted_content_id IS NULL)
        OR (accepted_plan_id IS NOT NULL AND accepted_content_id IS NOT NULL)
    ),
    CONSTRAINT concept_candidate_accepted_has_content CHECK (
        status <> 'accepted' OR accepted_content_id IS NOT NULL
    )
);

CREATE INDEX concept_candidates_review_idx
ON football_brief.concept_candidates (batch_id, status, total_score DESC, ordinal);

CREATE INDEX concept_candidates_duplicate_idx
ON football_brief.concept_candidates (concept_fingerprint, semantic_key);

CREATE INDEX concept_candidates_distribution_idx
ON football_brief.concept_candidates (batch_id, format, pillar, status);

CREATE TRIGGER concept_candidates_touch_updated_at
BEFORE UPDATE ON football_brief.concept_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.concept_slates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES football_brief.concept_generation_batches(id) ON DELETE RESTRICT,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    requested_count integer NOT NULL CHECK (requested_count >= 1),
    requested_format_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_pillar_targets jsonb NOT NULL DEFAULT '{}'::jsonb,
    actual_format_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
    actual_pillar_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
    gap_report jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'applied', 'superseded')),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    approved_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, version),
    CONSTRAINT concept_slate_approval_evidence CHECK (
        status = 'draft' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

CREATE TABLE football_brief.concept_slate_items (
    slate_id uuid NOT NULL REFERENCES football_brief.concept_slates(id) ON DELETE RESTRICT,
    candidate_id uuid NOT NULL REFERENCES football_brief.concept_candidates(id) ON DELETE RESTRICT,
    rank integer NOT NULL CHECK (rank >= 1),
    scheduled_for date,
    applied_content_id uuid REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (slate_id, candidate_id),
    UNIQUE (slate_id, rank),
    UNIQUE (slate_id, scheduled_for)
);

CREATE INDEX concept_slate_items_candidate_idx
ON football_brief.concept_slate_items (candidate_id);

CREATE OR REPLACE FUNCTION football_brief.protect_concept_candidate_generated_fields()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept candidates cannot be deleted';
    END IF;
    IF NEW.batch_id IS DISTINCT FROM OLD.batch_id
       OR NEW.ordinal IS DISTINCT FROM OLD.ordinal
       OR NEW.revised_from_candidate_id IS DISTINCT FROM OLD.revised_from_candidate_id
       OR NEW.title IS DISTINCT FROM OLD.title
       OR NEW.hook IS DISTINCT FROM OLD.hook
       OR NEW.concept IS DISTINCT FROM OLD.concept
       OR NEW.format IS DISTINCT FROM OLD.format
       OR NEW.pillar IS DISTINCT FROM OLD.pillar
       OR NEW.rationale IS DISTINCT FROM OLD.rationale
       OR NEW.source_requirements IS DISTINCT FROM OLD.source_requirements
       OR NEW.required_research IS DISTINCT FROM OLD.required_research
       OR NEW.factual_risk IS DISTINCT FROM OLD.factual_risk
       OR NEW.production_complexity IS DISTINCT FROM OLD.production_complexity
       OR NEW.estimated_cost_usd IS DISTINCT FROM OLD.estimated_cost_usd
       OR NEW.recommended_route IS DISTINCT FROM OLD.recommended_route
       OR NEW.concept_fingerprint IS DISTINCT FROM OLD.concept_fingerprint
       OR NEW.semantic_key IS DISTINCT FROM OLD.semantic_key
       OR NEW.semantic_tokens IS DISTINCT FROM OLD.semantic_tokens
       OR NEW.duplicate_content_id IS DISTINCT FROM OLD.duplicate_content_id
       OR NEW.duplicate_candidate_id IS DISTINCT FROM OLD.duplicate_candidate_id
       OR NEW.duplicate_kind IS DISTINCT FROM OLD.duplicate_kind
       OR NEW.duplicate_similarity IS DISTINCT FROM OLD.duplicate_similarity
       OR NEW.originality_score IS DISTINCT FROM OLD.originality_score
       OR NEW.engagement_score IS DISTINCT FROM OLD.engagement_score
       OR NEW.monetization_fit_score IS DISTINCT FROM OLD.monetization_fit_score
       OR NEW.policy_risk_score IS DISTINCT FROM OLD.policy_risk_score
       OR NEW.feasibility_score IS DISTINCT FROM OLD.feasibility_score
       OR NEW.total_score IS DISTINCT FROM OLD.total_score
       OR NEW.score_evidence IS DISTINCT FROM OLD.score_evidence
       OR NEW.generation_evidence IS DISTINCT FROM OLD.generation_evidence
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Generated concept candidate fields are immutable; create a revision candidate';
    END IF;
    IF OLD.status IN ('accepted', 'superseded', 'duplicate_blocked')
       AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'Terminal concept candidate status is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_candidate_generated_fields_immutable
BEFORE UPDATE OR DELETE ON football_brief.concept_candidates
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_concept_candidate_generated_fields();

CREATE OR REPLACE FUNCTION football_brief.protect_concept_slate_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Concept slates and slate items cannot be deleted';
    END IF;
    IF TG_TABLE_NAME = 'concept_slates' AND OLD.status <> 'draft' THEN
        RAISE EXCEPTION 'Approved and applied concept slates are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER concept_slate_immutable
BEFORE UPDATE OR DELETE ON football_brief.concept_slates
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_concept_slate_evidence();

CREATE TRIGGER concept_slate_item_immutable
BEFORE UPDATE OR DELETE ON football_brief.concept_slate_items
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_concept_slate_evidence();

COMMENT ON TABLE football_brief.concept_generation_batches IS
    'Operator-triggered local or deterministic generation only. paid_provider_allowed is permanently false.';
COMMENT ON TABLE football_brief.concept_candidates IS
    'Reviewable scored candidates. Generation never inserts them into an active monthly plan.';
COMMENT ON TABLE football_brief.concept_slates IS
    'Balanced shortlist snapshots with requested and actual format/pillar distributions plus explicit gaps.';

COMMIT;
