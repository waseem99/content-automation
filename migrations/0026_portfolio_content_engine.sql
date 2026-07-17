-- Multi-brand rolling content portfolio, platform packaging, reuse, and analytics
-- Depends on migrations/0001_phase0_asset_rights.sql and 0002_phase1_workflow_foundation.sql

BEGIN;

CREATE TABLE football_brief.brands (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    display_name text NOT NULL,
    niche text NOT NULL,
    primary_platform text NOT NULL DEFAULT 'facebook',
    content_mode text NOT NULL CHECK (content_mode IN ('video', 'mixed', 'still')),
    monthly_target integer NOT NULL CHECK (monthly_target BETWEEN 1 AND 180),
    source_links jsonb NOT NULL DEFAULT '[]'::jsonb,
    content_pillars jsonb NOT NULL DEFAULT '[]'::jsonb,
    active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER brands_touch_updated_at BEFORE UPDATE ON football_brief.brands
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.monthly_content_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    month_start date NOT NULL CHECK (month_start = date_trunc('month', month_start)::date),
    target_count integer NOT NULL CHECK (target_count > 0),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'complete', 'archived')),
    strategy jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_id, month_start)
);

CREATE TRIGGER monthly_plans_touch_updated_at BEFORE UPDATE ON football_brief.monthly_content_plans
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.portfolio_content (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES football_brief.monthly_content_plans(id) ON DELETE RESTRICT,
    content_item_id uuid REFERENCES football_brief.content_items(id) ON DELETE RESTRICT,
    scheduled_for date NOT NULL,
    title text NOT NULL,
    concept text NOT NULL,
    format text NOT NULL,
    stage text NOT NULL DEFAULT 'idea' CHECK (stage IN (
        'idea', 'script', 'preview', 'premium', 'package', 'ready', 'published', 'blocked', 'archived'
    )),
    concept_fingerprint char(64) NOT NULL,
    semantic_key text NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    script jsonb,
    voiceover jsonb,
    scene_plan jsonb,
    preview_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    premium_budget_usd numeric(12,4) CHECK (premium_budget_usd IS NULL OR premium_budget_usd >= 0),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (plan_id, scheduled_for, semantic_key),
    UNIQUE (plan_id, concept_fingerprint)
);

CREATE INDEX portfolio_content_queue_idx ON football_brief.portfolio_content (plan_id, stage, scheduled_for);
CREATE INDEX portfolio_content_duplicate_idx ON football_brief.portfolio_content (concept_fingerprint, semantic_key);
CREATE TRIGGER portfolio_content_touch_updated_at BEFORE UPDATE ON football_brief.portfolio_content
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.portfolio_approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    gate text NOT NULL CHECK (gate IN ('idea', 'script', 'preview', 'premium_spend', 'package', 'publish')),
    decision text NOT NULL CHECK (decision IN ('approved', 'changes_requested', 'rejected')),
    reviewer text NOT NULL,
    rationale text NOT NULL,
    content_version integer NOT NULL CHECK (content_version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_content_id, gate, content_version, reviewer)
);

CREATE TABLE football_brief.reusable_clips (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    asset_id uuid NOT NULL REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    semantic_key text NOT NULL,
    description text NOT NULL,
    reuse_scope text NOT NULL DEFAULT 'same_brand' CHECK (reuse_scope IN ('same_brand', 'portfolio', 'single_use')),
    max_uses integer NOT NULL DEFAULT 3 CHECK (max_uses BETWEEN 1 AND 20),
    use_count integer NOT NULL DEFAULT 0 CHECK (use_count >= 0),
    last_used_at timestamptz,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (asset_id, semantic_key)
);

CREATE TABLE football_brief.platform_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    platform text NOT NULL CHECK (platform IN ('facebook', 'youtube_shorts', 'youtube', 'tiktok', 'instagram')),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    video_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    thumbnail_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    title text NOT NULL,
    caption text NOT NULL,
    hashtags jsonb NOT NULL DEFAULT '[]'::jsonb,
    disclosure jsonb NOT NULL DEFAULT '{}'::jsonb,
    package_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'published', 'superseded')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_content_id, platform, version)
);

CREATE TABLE football_brief.performance_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_package_id uuid NOT NULL REFERENCES football_brief.platform_packages(id) ON DELETE RESTRICT,
    observed_at timestamptz NOT NULL,
    views bigint CHECK (views IS NULL OR views >= 0),
    watch_seconds numeric(16,3) CHECK (watch_seconds IS NULL OR watch_seconds >= 0),
    average_view_percentage numeric(7,4) CHECK (average_view_percentage IS NULL OR average_view_percentage BETWEEN 0 AND 100),
    three_second_view_rate numeric(7,4) CHECK (three_second_view_rate IS NULL OR three_second_view_rate BETWEEN 0 AND 100),
    engagements bigint CHECK (engagements IS NULL OR engagements >= 0),
    shares bigint CHECK (shares IS NULL OR shares >= 0),
    followers_gained bigint CHECK (followers_gained IS NULL OR followers_gained >= 0),
    revenue_usd numeric(14,4) CHECK (revenue_usd IS NULL OR revenue_usd >= 0),
    source text NOT NULL DEFAULT 'manual',
    raw_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (platform_package_id, observed_at)
);

COMMENT ON TABLE football_brief.reusable_clips IS
    'Rights-cleared shot inventory. Reuse is capped and never substitutes for originality review.';
COMMENT ON TABLE football_brief.performance_observations IS
    'Append-only analytics observations. Metrics advise future plans and never auto-approve publishing.';

COMMIT;
