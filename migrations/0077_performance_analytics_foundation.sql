-- Append-only performance observations, controlled variants, and advisory learning evidence.

BEGIN;

CREATE TABLE football_brief.performance_import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    platform text NOT NULL CHECK (length(btrim(platform)) BETWEEN 2 AND 80),
    source_system text NOT NULL CHECK (length(btrim(source_system)) BETWEEN 2 AND 120),
    source_account_ref text NOT NULL CHECK (length(btrim(source_account_ref)) BETWEEN 3 AND 240),
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) BETWEEN 8 AND 240),
    source_digest char(64) NOT NULL,
    observed_from timestamptz NOT NULL,
    observed_to timestamptz NOT NULL,
    row_count integer NOT NULL CHECK (row_count>=1),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
    imported_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (observed_to>=observed_from)
);

CREATE INDEX performance_import_batches_brand_idx
ON football_brief.performance_import_batches(brand_id,platform,observed_to DESC);

CREATE TABLE football_brief.performance_delivery_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id uuid NOT NULL
        REFERENCES football_brief.performance_import_batches(id) ON DELETE RESTRICT,
    source_observation_id text NOT NULL CHECK (length(btrim(source_observation_id)) BETWEEN 1 AND 500),
    observation_fingerprint char(64) NOT NULL UNIQUE,
    delivery_request_id uuid NOT NULL
        REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    final_release_id uuid NOT NULL
        REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    content_version integer NOT NULL CHECK (content_version>=1),
    platform text NOT NULL CHECK (length(btrim(platform)) BETWEEN 2 AND 80),
    post_reference text NOT NULL CHECK (length(btrim(post_reference)) BETWEEN 1 AND 2000),
    post_status text NOT NULL CHECK (post_status IN (
        'draft','scheduled','published','failed','deleted','private','unlisted','unknown'
    )),
    observed_at timestamptz NOT NULL,
    window_seconds bigint NOT NULL CHECK (window_seconds>=0),
    views bigint NOT NULL DEFAULT 0 CHECK (views>=0),
    normalized_views bigint NOT NULL DEFAULT 0 CHECK (normalized_views>=0),
    retention_rate numeric(9,6) CHECK (retention_rate IS NULL OR retention_rate BETWEEN 0 AND 1),
    completion_rate numeric(9,6) CHECK (completion_rate IS NULL OR completion_rate BETWEEN 0 AND 1),
    rewatch_rate numeric(9,6) CHECK (rewatch_rate IS NULL OR rewatch_rate BETWEEN 0 AND 1),
    engagement_count bigint NOT NULL DEFAULT 0 CHECK (engagement_count>=0),
    engagement_rate numeric(9,6) CHECK (engagement_rate IS NULL OR engagement_rate BETWEEN 0 AND 1),
    shares bigint NOT NULL DEFAULT 0 CHECK (shares>=0),
    follower_growth bigint NOT NULL DEFAULT 0,
    revenue_amount numeric(18,6) NOT NULL DEFAULT 0 CHECK (revenue_amount>=0),
    revenue_currency char(3) NOT NULL DEFAULT 'USD' CHECK (revenue_currency ~ '^[A-Z]{3}$'),
    revenue_usd numeric(18,6) NOT NULL DEFAULT 0 CHECK (revenue_usd>=0),
    production_cost_usd numeric(18,6) NOT NULL CHECK (production_cost_usd>=0),
    creative_snapshot jsonb NOT NULL CHECK (jsonb_typeof(creative_snapshot)='object'),
    metric_source_snapshot jsonb NOT NULL CHECK (jsonb_typeof(metric_source_snapshot)='object'),
    imported_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (import_batch_id,source_observation_id),
    UNIQUE (delivery_request_id,observed_at,window_seconds)
);

CREATE INDEX performance_delivery_observations_content_idx
ON football_brief.performance_delivery_observations(brand_id,portfolio_content_id,observed_at DESC);

CREATE INDEX performance_delivery_observations_delivery_idx
ON football_brief.performance_delivery_observations(delivery_request_id,observed_at DESC);

CREATE TABLE football_brief.performance_experiments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    experiment_key text NOT NULL CHECK (experiment_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 3 AND 200),
    version integer NOT NULL CHECK (version>=1),
    parent_experiment_id uuid REFERENCES football_brief.performance_experiments(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','active','completed','cancelled','superseded'
    )),
    hypothesis text NOT NULL CHECK (length(btrim(hypothesis)) BETWEEN 10 AND 5000),
    winner_criteria jsonb NOT NULL CHECK (jsonb_typeof(winner_criteria)='object'),
    minimum_observation_count integer NOT NULL DEFAULT 2 CHECK (minimum_observation_count>=1),
    minimum_views_per_variant bigint NOT NULL DEFAULT 1000 CHECK (minimum_views_per_variant>=0),
    significance_threshold numeric(7,6) NOT NULL DEFAULT 0.950000
        CHECK (significance_threshold>0 AND significance_threshold<=1),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    completed_at timestamptz,
    cancelled_at timestamptz,
    UNIQUE (brand_id,experiment_key,version),
    CHECK (version=1 OR parent_experiment_id IS NOT NULL),
    CHECK (version<>1 OR parent_experiment_id IS NULL)
);

CREATE UNIQUE INDEX performance_experiment_one_active_idx
ON football_brief.performance_experiments(brand_id,experiment_key)
WHERE status='active';

CREATE TABLE football_brief.performance_experiment_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id uuid NOT NULL
        REFERENCES football_brief.performance_experiments(id) ON DELETE RESTRICT,
    variant_key text NOT NULL CHECK (variant_key ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
    label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 200),
    final_release_id uuid NOT NULL REFERENCES football_brief.final_releases(id) ON DELETE RESTRICT,
    delivery_request_id uuid NOT NULL
        REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    declared_changes jsonb NOT NULL CHECK (jsonb_typeof(declared_changes)='object'),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id,variant_key),
    UNIQUE (experiment_id,final_release_id),
    UNIQUE (experiment_id,delivery_request_id)
);

CREATE INDEX performance_experiment_variants_release_idx
ON football_brief.performance_experiment_variants(final_release_id,delivery_request_id);

CREATE TABLE football_brief.performance_experiment_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id uuid NOT NULL
        REFERENCES football_brief.performance_experiments(id) ON DELETE RESTRICT,
    evaluation_sequence integer NOT NULL CHECK (evaluation_sequence>=1),
    result_status text NOT NULL CHECK (result_status IN (
        'insufficient_data','meaningful_result','no_winner'
    )),
    winner_variant_id uuid REFERENCES football_brief.performance_experiment_variants(id) ON DELETE RESTRICT,
    evaluated_observation_ids uuid[] NOT NULL CHECK (cardinality(evaluated_observation_ids)>=1),
    criteria_snapshot jsonb NOT NULL CHECK (jsonb_typeof(criteria_snapshot)='object'),
    metric_summary jsonb NOT NULL CHECK (jsonb_typeof(metric_summary)='object'),
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    evaluated_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id,evaluation_sequence),
    CHECK (result_status<>'meaningful_result' OR winner_variant_id IS NOT NULL),
    CHECK (result_status='meaningful_result' OR winner_variant_id IS NULL)
);

CREATE TABLE football_brief.performance_recommendations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    experiment_result_id uuid REFERENCES football_brief.performance_experiment_results(id) ON DELETE RESTRICT,
    recommendation_key text NOT NULL CHECK (length(btrim(recommendation_key)) BETWEEN 3 AND 160),
    recommendation text NOT NULL CHECK (length(btrim(recommendation)) BETWEEN 10 AND 5000),
    cited_observation_ids uuid[] NOT NULL CHECK (cardinality(cited_observation_ids)>=1),
    metric_citations jsonb NOT NULL CHECK (jsonb_typeof(metric_citations)='array'),
    confidence text NOT NULL CHECK (confidence IN ('low','medium','high')),
    advisory_only boolean NOT NULL DEFAULT true CHECK (advisory_only=true),
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_id,recommendation_key,created_at)
);

CREATE OR REPLACE VIEW football_brief.performance_delivery_observation_economics AS
SELECT po.*,
       CASE WHEN po.normalized_views>0
            THEN round((po.production_cost_usd/po.normalized_views)*1000,6)
            ELSE NULL END AS cost_per_thousand_views_usd,
       CASE WHEN po.normalized_views>0
            THEN round((po.revenue_usd/po.normalized_views)*1000,6)
            ELSE NULL END AS revenue_per_thousand_views_usd,
       po.production_cost_usd AS cost_per_item_usd,
       round(po.revenue_usd-po.production_cost_usd,6) AS contribution_after_production_cost_usd
FROM football_brief.performance_delivery_observations po;

COMMENT ON TABLE football_brief.performance_delivery_observations IS
    'Append-only normalized platform observations tied to exact successful delivery and release lineage.';
COMMENT ON TABLE football_brief.performance_experiment_results IS
    'Append-only controlled-variant evaluations that explicitly distinguish insufficient data, no winner, and meaningful results.';
COMMENT ON TABLE football_brief.performance_recommendations IS
    'Metric-citing advisory evidence only; this table cannot approve, generate, schedule, or deliver content.';

COMMIT;
