-- Ensure legacy portfolio insertion paths create a valid P110 master family automatically.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.initialize_content_family()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_family uuid;
BEGIN
    IF NEW.variant_type = 'master' THEN
        NEW.content_family_id := COALESCE(NEW.content_family_id, NEW.id);
        NEW.parent_content_id := NULL;
        NEW.short_cut_index := NULL;
    ELSE
        IF NEW.parent_content_id IS NULL THEN
            RAISE EXCEPTION 'Adaptations and short cuts require a parent master content item';
        END IF;
        SELECT pc.content_family_id INTO parent_family
          FROM football_brief.portfolio_content pc
         WHERE pc.id=NEW.parent_content_id;
        IF parent_family IS NULL THEN
            RAISE EXCEPTION 'Parent content family was not found';
        END IF;
        NEW.content_family_id := COALESCE(NEW.content_family_id, parent_family);
    END IF;

    IF COALESCE(array_length(NEW.target_platforms,1),0) = 0 THEN
        NEW.target_platforms := ARRAY[COALESCE(NULLIF(NEW.primary_platform,''),'facebook')]::text[];
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER portfolio_content_family_defaults
BEFORE INSERT ON football_brief.portfolio_content
FOR EACH ROW EXECUTE FUNCTION football_brief.initialize_content_family();

COMMIT;
