-- P110 four-brand, research-backed, multi-platform production expansion.
-- Forward-only: existing content becomes a self-contained master family and keeps all history.

BEGIN;

CREATE TABLE football_brief.brand_review_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    policy_key text NOT NULL CHECK (policy_key IN (
        'independent_review_required',
        'admin_self_review_allowed',
        'independent_final_release_required'
    )),
    active boolean NOT NULL DEFAULT false,
    rationale_required_for_override boolean NOT NULL DEFAULT false,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (brand_id, version),
    CONSTRAINT active_review_policy_has_activation CHECK (
        active = false OR activated_at IS NOT NULL
    )
);

CREATE UNIQUE INDEX brand_review_policies_one_active_idx
ON football_brief.brand_review_policies (brand_id)
WHERE active = true;

CREATE INDEX brand_review_policies_history_idx
ON football_brief.brand_review_policies (brand_id, version DESC);

-- Review policies are seeded by the idempotent local onboarding step after
-- operator identities exist. Migrations never invent login or audit actors.

ALTER TABLE football_brief.portfolio_content
    ADD COLUMN content_family_id uuid,
    ADD COLUMN parent_content_id uuid,
    ADD COLUMN variant_type text NOT NULL DEFAULT 'master'
        CHECK (variant_type IN ('master','adaptation','short_cut')),
    ADD COLUMN primary_platform text NOT NULL DEFAULT 'facebook',
    ADD COLUMN target_platforms text[] NOT NULL DEFAULT ARRAY['facebook']::text[],
    ADD COLUMN target_duration_seconds integer NOT NULL DEFAULT 45
        CHECK (target_duration_seconds BETWEEN 10 AND 150),
    ADD COLUMN short_cut_index integer,
    ADD COLUMN adaptation_profile jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD CONSTRAINT portfolio_content_short_cut_index_valid CHECK (
        (variant_type='short_cut' AND short_cut_index BETWEEN 1 AND 2)
        OR (variant_type<>'short_cut' AND short_cut_index IS NULL)
    );

UPDATE football_brief.portfolio_content pc
SET content_family_id = pc.id,
    primary_platform = COALESCE(NULLIF(b.primary_platform,''),'facebook'),
    target_platforms = ARRAY[COALESCE(NULLIF(b.primary_platform,''),'facebook')]::text[],
    target_duration_seconds = CASE
        WHEN COALESCE(pc.metadata #>> '{studio_v2_brief,duration_seconds}','') ~ '^[0-9]+$'
          AND (pc.metadata #>> '{studio_v2_brief,duration_seconds}')::integer BETWEEN 10 AND 150
        THEN (pc.metadata #>> '{studio_v2_brief,duration_seconds}')::integer
        ELSE 45
    END
FROM football_brief.monthly_content_plans mp
JOIN football_brief.brands b ON b.id=mp.brand_id
WHERE mp.id=pc.plan_id;

ALTER TABLE football_brief.portfolio_content
    ALTER COLUMN content_family_id SET NOT NULL,
    ADD CONSTRAINT portfolio_content_family_fk
        FOREIGN KEY (content_family_id) REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    ADD CONSTRAINT portfolio_content_parent_fk
        FOREIGN KEY (parent_content_id) REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    ADD CONSTRAINT portfolio_content_family_shape CHECK (
        (variant_type='master' AND parent_content_id IS NULL AND content_family_id=id)
        OR (variant_type IN ('adaptation','short_cut') AND parent_content_id IS NOT NULL AND content_family_id<>id)
    );

CREATE INDEX portfolio_content_family_idx
ON football_brief.portfolio_content (content_family_id, variant_type, short_cut_index, scheduled_for, id);

CREATE UNIQUE INDEX portfolio_content_one_platform_adaptation_idx
ON football_brief.portfolio_content (content_family_id, primary_platform)
WHERE variant_type='adaptation';

CREATE UNIQUE INDEX portfolio_content_short_cut_slot_idx
ON football_brief.portfolio_content (content_family_id, short_cut_index)
WHERE variant_type='short_cut';

CREATE TABLE football_brief.script_source_research_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    script_document_id uuid NOT NULL REFERENCES football_brief.script_documents(id) ON DELETE RESTRICT,
    script_version_id uuid NOT NULL REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    claim_id uuid NOT NULL,
    query text NOT NULL CHECK (length(btrim(query)) BETWEEN 3 AND 2000),
    provider text NOT NULL CHECK (length(btrim(provider)) BETWEEN 2 AND 100),
    provider_model text,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed','no_results')),
    result_count integer NOT NULL DEFAULT 0 CHECK (result_count >= 0 AND result_count <= 20),
    error_code text,
    requested_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    retrieval_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (claim_id, script_version_id)
        REFERENCES football_brief.script_claims(id, script_version_id) ON DELETE RESTRICT,
    FOREIGN KEY (script_version_id, script_document_id)
        REFERENCES football_brief.script_versions(id, script_document_id) ON DELETE RESTRICT
);

CREATE INDEX script_source_research_runs_claim_idx
ON football_brief.script_source_research_runs (claim_id, requested_at DESC);

CREATE TABLE football_brief.script_source_research_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id uuid NOT NULL REFERENCES football_brief.script_source_research_runs(id) ON DELETE RESTRICT,
    rank integer NOT NULL CHECK (rank BETWEEN 1 AND 20),
    title text NOT NULL CHECK (length(btrim(title)) >= 3),
    publisher text,
    canonical_url text NOT NULL CHECK (
        canonical_url ~* '^https://' AND canonical_url !~* '(token|signature|password|secret|cookie)='
    ),
    published_on date,
    source_type text NOT NULL CHECK (source_type IN (
        'primary','government','academic','secondary','news','expert','internal_reference'
    )),
    quality_score numeric(5,2) NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    relevance_summary text NOT NULL CHECK (length(btrim(relevance_summary)) >= 3),
    evidence_locator text,
    evidence_digest char(64) NOT NULL,
    rights_declaration text NOT NULL DEFAULT 'publicly_accessible' CHECK (rights_declaration IN (
        'owned','licensed','publicly_accessible','quotation_only','internal_research'
    )),
    permitted_use text NOT NULL CHECK (length(btrim(permitted_use)) >= 3),
    validation_status text NOT NULL DEFAULT 'pending' CHECK (validation_status IN ('pending','valid','invalid')),
    validated_at timestamptz,
    accepted_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    accepted_at timestamptz,
    rejected_by text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rejected_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (research_run_id, rank),
    UNIQUE (research_run_id, canonical_url),
    CONSTRAINT research_candidate_decision_consistent CHECK (
        NOT (accepted_at IS NOT NULL AND rejected_at IS NOT NULL)
        AND (accepted_at IS NULL OR accepted_by IS NOT NULL)
        AND (rejected_at IS NULL OR rejected_by IS NOT NULL)
    )
);

CREATE INDEX script_source_research_candidates_run_idx
ON football_brief.script_source_research_candidates (research_run_id, rank);

ALTER TABLE football_brief.script_review_decisions
    ADD COLUMN self_review boolean NOT NULL DEFAULT false,
    ADD COLUMN review_policy_key text NOT NULL DEFAULT 'independent_review_required'
        CHECK (review_policy_key IN (
            'independent_review_required',
            'admin_self_review_allowed',
            'independent_final_release_required'
        )),
    ADD COLUMN override_reason text;

CREATE OR REPLACE FUNCTION football_brief.validate_script_review_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_version_id uuid;
    current_lock_version bigint;
    version_status text;
    version_last_editor text;
    review_brand_id uuid;
    active_policy text;
    reviewer_is_admin boolean;
BEGIN
    SELECT sd.current_version_id, sd.lock_version, sv.status, sv.last_edited_by, mp.brand_id
      INTO current_version_id, current_lock_version, version_status, version_last_editor, review_brand_id
      FROM football_brief.script_documents sd
      JOIN football_brief.script_versions sv
        ON sv.id = NEW.script_version_id
       AND sv.script_document_id = sd.id
      JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
      JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
     WHERE sd.id = NEW.script_document_id
     FOR UPDATE OF sd, sv;

    IF current_version_id IS DISTINCT FROM NEW.script_version_id THEN
        RAISE EXCEPTION 'Stale script versions cannot be reviewed';
    END IF;
    IF version_status IS DISTINCT FROM 'in_review' THEN
        RAISE EXCEPTION 'Only submitted script versions can be reviewed';
    END IF;
    IF current_lock_version IS DISTINCT FROM NEW.document_lock_version THEN
        RAISE EXCEPTION 'Script review lock version is stale';
    END IF;

    SELECT p.policy_key INTO active_policy
      FROM football_brief.brand_review_policies p
     WHERE p.brand_id=review_brand_id AND p.active=true
     ORDER BY p.version DESC LIMIT 1;
    active_policy := COALESCE(active_policy,'independent_review_required');

    SELECT EXISTS (
        SELECT 1
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_user_roles ur ON ur.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.reviewer_operator_id
           AND ou.active=true
           AND ur.role IN ('admin','super_admin')
    ) INTO reviewer_is_admin;

    IF version_last_editor = NEW.reviewer_operator_id THEN
        IF NEW.self_review IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Independent script review is required';
        END IF;
        IF reviewer_is_admin IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Admin role is required for script self-review';
        END IF;
        IF active_policy NOT IN ('admin_self_review_allowed','independent_final_release_required') THEN
            RAISE EXCEPTION 'Brand review policy requires independent script review';
        END IF;
    ELSIF NEW.self_review = true THEN
        IF reviewer_is_admin IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Admin role is required for script self-review';
        END IF;
        IF active_policy NOT IN ('admin_self_review_allowed','independent_final_release_required') THEN
            RAISE EXCEPTION 'Brand review policy requires independent script review';
        END IF;
    END IF;

    IF NEW.review_policy_key IS DISTINCT FROM active_policy THEN
        RAISE EXCEPTION 'Script review policy version is stale';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON TABLE football_brief.brand_review_policies IS
    'Versioned brand decision policy. Admin self-review is explicit and never represented as independent review.';
COMMENT ON TABLE football_brief.script_source_research_runs IS
    'Operator-triggered web research lineage for one exact script claim and version.';
COMMENT ON COLUMN football_brief.portfolio_content.content_family_id IS
    'Canonical master content ID shared by all linked platform adaptations and short cuts.';
COMMENT ON COLUMN football_brief.script_review_decisions.self_review IS
    'True only when an eligible Admin explicitly reviewed a version they last edited under the active brand policy.';

COMMIT;
