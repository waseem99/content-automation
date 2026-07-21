-- Football Brief versioned brand profiles and approved narration preset assignments.
-- Voice rights and consent remain canonical in football_brief.approved_voices.

BEGIN;

CREATE TABLE football_brief.brand_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
    default_language text NOT NULL DEFAULT 'en' CHECK (default_language ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$'),
    audience jsonb NOT NULL DEFAULT '{}'::jsonb,
    tone text NOT NULL CHECK (length(btrim(tone)) BETWEEN 3 AND 500),
    visual_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_restrictions jsonb NOT NULL DEFAULT '{}'::jsonb,
    cadence jsonb NOT NULL DEFAULT '{}'::jsonb,
    platforms text[] NOT NULL DEFAULT ARRAY[]::text[],
    budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    activated_by text,
    activated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_id, version),
    CONSTRAINT active_brand_profile_has_activator CHECK (
        status <> 'active' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX brand_profiles_one_active_idx
ON football_brief.brand_profiles (brand_id)
WHERE status = 'active';

CREATE INDEX brand_profiles_brand_history_idx
ON football_brief.brand_profiles (brand_id, version DESC);

CREATE TRIGGER brand_profiles_touch_updated_at
BEFORE UPDATE ON football_brief.brand_profiles
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.brand_narration_presets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_profile_id uuid NOT NULL REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    preset_key text NOT NULL CHECK (preset_key ~ '^[a-z0-9][a-z0-9_-]{1,39}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 120),
    role text NOT NULL CHECK (role IN ('primary', 'energetic', 'serious')),
    approved_voice_id uuid NOT NULL REFERENCES football_brief.approved_voices(id) ON DELETE RESTRICT,
    language text NOT NULL CHECK (language ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$'),
    speed numeric(4,3) NOT NULL DEFAULT 1.000 CHECK (speed BETWEEN 0.500 AND 2.000),
    style jsonb NOT NULL DEFAULT '{}'::jsonb,
    pronunciation_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    format_filters text[] NOT NULL DEFAULT ARRAY[]::text[],
    topic_filters text[] NOT NULL DEFAULT ARRAY[]::text[],
    is_default boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (brand_profile_id, preset_key),
    UNIQUE (brand_profile_id, role)
);

CREATE UNIQUE INDEX brand_narration_one_default_idx
ON football_brief.brand_narration_presets (brand_profile_id)
WHERE is_default = true AND active = true;

CREATE INDEX brand_narration_selection_idx
ON football_brief.brand_narration_presets (brand_profile_id, language, active);

CREATE OR REPLACE FUNCTION football_brief.enforce_brand_narration_preset_limit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    active_count integer;
BEGIN
    IF NEW.active = false THEN
        RETURN NEW;
    END IF;
    SELECT count(*) INTO active_count
      FROM football_brief.brand_narration_presets
     WHERE brand_profile_id = NEW.brand_profile_id
       AND active = true
       AND id <> NEW.id;
    IF active_count >= 3 THEN
        RAISE EXCEPTION 'A brand profile can have at most three active narration presets';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER brand_narration_preset_limit
BEFORE INSERT OR UPDATE ON football_brief.brand_narration_presets
FOR EACH ROW EXECUTE FUNCTION football_brief.enforce_brand_narration_preset_limit();

ALTER TABLE football_brief.portfolio_content
    ADD COLUMN brand_profile_id uuid REFERENCES football_brief.brand_profiles(id) ON DELETE RESTRICT,
    ADD COLUMN narration_preset_id uuid REFERENCES football_brief.brand_narration_presets(id) ON DELETE RESTRICT,
    ADD CONSTRAINT narration_preset_requires_profile CHECK (
        narration_preset_id IS NULL OR brand_profile_id IS NOT NULL
    );

COMMENT ON TABLE football_brief.brand_profiles IS
    'Immutable-on-activation versioned brand operating settings; new changes create a new version.';
COMMENT ON TABLE football_brief.brand_narration_presets IS
    'One to three brand-scoped narration assignments referencing the canonical approved voice registry.';
COMMENT ON COLUMN football_brief.portfolio_content.narration_preset_id IS
    'Pinned preset version used by this content item so later brand changes do not rewrite history.';

COMMIT;
