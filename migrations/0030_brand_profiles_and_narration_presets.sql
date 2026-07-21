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
    PERFORM 1 FROM football_brief.brand_profiles WHERE id = NEW.brand_profile_id FOR UPDATE;
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

CREATE OR REPLACE FUNCTION football_brief.protect_brand_profile_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IN ('active', 'retired') THEN
        IF NEW.brand_id IS DISTINCT FROM OLD.brand_id
           OR NEW.version IS DISTINCT FROM OLD.version
           OR NEW.default_language IS DISTINCT FROM OLD.default_language
           OR NEW.audience IS DISTINCT FROM OLD.audience
           OR NEW.tone IS DISTINCT FROM OLD.tone
           OR NEW.visual_rules IS DISTINCT FROM OLD.visual_rules
           OR NEW.content_restrictions IS DISTINCT FROM OLD.content_restrictions
           OR NEW.cadence IS DISTINCT FROM OLD.cadence
           OR NEW.platforms IS DISTINCT FROM OLD.platforms
           OR NEW.budget IS DISTINCT FROM OLD.budget
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR (OLD.status = 'retired' AND NEW.status <> 'retired')
           OR (OLD.status = 'active' AND NEW.status NOT IN ('active', 'retired')) THEN
            RAISE EXCEPTION 'Active and retired brand profile versions are immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER brand_profile_version_immutable
BEFORE UPDATE ON football_brief.brand_profiles
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_brand_profile_version();

CREATE OR REPLACE FUNCTION football_brief.protect_brand_narration_preset()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    profile_status text;
    profile_id uuid;
BEGIN
    profile_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.brand_profile_id ELSE NEW.brand_profile_id END;
    SELECT status INTO profile_status FROM football_brief.brand_profiles WHERE id = profile_id FOR UPDATE;
    IF profile_status <> 'draft' THEN
        RAISE EXCEPTION 'Narration presets are immutable after brand profile activation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

CREATE TRIGGER brand_narration_preset_immutable
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.brand_narration_presets
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_brand_narration_preset();

CREATE OR REPLACE FUNCTION football_brief.validate_brand_profile_activation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    preset_count integer;
    default_count integer;
    invalid_voice_count integer;
BEGIN
    IF OLD.status = 'draft' AND NEW.status = 'active' THEN
        SELECT count(*), count(*) FILTER (WHERE is_default = true)
          INTO preset_count, default_count
          FROM football_brief.brand_narration_presets
         WHERE brand_profile_id = NEW.id AND active = true;
        IF preset_count < 1 OR preset_count > 3 OR default_count <> 1 THEN
            RAISE EXCEPTION 'Active brand profiles require one to three presets and exactly one default';
        END IF;
        SELECT count(*) INTO invalid_voice_count
          FROM football_brief.brand_narration_presets p
          JOIN football_brief.approved_voices v ON v.id = p.approved_voice_id
         WHERE p.brand_profile_id = NEW.id
           AND p.active = true
           AND (v.approval_status <> 'approved' OR (v.expires_at IS NOT NULL AND v.expires_at <= now()));
        IF invalid_voice_count > 0 THEN
            RAISE EXCEPTION 'Active brand profiles cannot reference unapproved or expired voices';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER brand_profile_activation_valid
BEFORE UPDATE ON football_brief.brand_profiles
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_brand_profile_activation();

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
