-- Bind final release identity, narration input, assembly, and approval to the exact approved P90 audio mix.

BEGIN;

ALTER TABLE football_brief.final_releases
    ADD COLUMN audio_mix_version_id uuid NOT NULL
        REFERENCES football_brief.audio_mix_versions(id) ON DELETE RESTRICT;

CREATE INDEX final_releases_audio_mix_idx
ON football_brief.final_releases(audio_mix_version_id);

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_audio_mix()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    mix_row football_brief.audio_mix_versions%ROWTYPE;
    production_row football_brief.audio_productions%ROWTYPE;
    final_asset_row football_brief.assets%ROWTYPE;
BEGIN
    IF TG_OP='UPDATE' AND NEW.audio_mix_version_id IS DISTINCT FROM OLD.audio_mix_version_id THEN
        RAISE EXCEPTION 'Final release audio mix identity is immutable';
    END IF;

    SELECT * INTO mix_row
      FROM football_brief.audio_mix_versions
     WHERE id=COALESCE(NEW.audio_mix_version_id,OLD.audio_mix_version_id);
    SELECT * INTO production_row
      FROM football_brief.audio_productions
     WHERE id=mix_row.audio_production_id;
    SELECT * INTO final_asset_row
      FROM football_brief.assets
     WHERE id=mix_row.final_mix_asset_id;

    IF mix_row.id IS NULL
       OR mix_row.status<>'approved'
       OR mix_row.alignment_source<>'forced_alignment'
       OR mix_row.qc_status<>'pass'
       OR production_row.id IS NULL
       OR production_row.current_mix_version_id IS DISTINCT FROM mix_row.id
       OR production_row.status<>'approved'
       OR production_row.portfolio_content_id IS DISTINCT FROM COALESCE(NEW.portfolio_content_id,OLD.portfolio_content_id)
       OR production_row.content_version IS DISTINCT FROM COALESCE(NEW.content_version,OLD.content_version)
       OR final_asset_row.id IS NULL
       OR final_asset_row.asset_type<>'audio'
       OR final_asset_row.lifecycle_status<>'approved' THEN
        RAISE EXCEPTION 'Final release requires the current approved QC-passing forced-alignment audio mix';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_audio_mix_valid
BEFORE INSERT OR UPDATE ON football_brief.final_releases
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_audio_mix();

CREATE OR REPLACE FUNCTION football_brief.validate_final_release_narration_mix_asset()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_mix uuid;
    expected_final_asset uuid;
BEGIN
    IF NEW.role<>'narration' THEN
        RETURN NEW;
    END IF;

    SELECT fr.audio_mix_version_id,amv.final_mix_asset_id
      INTO release_mix,expected_final_asset
      FROM football_brief.final_releases fr
      JOIN football_brief.audio_mix_versions amv ON amv.id=fr.audio_mix_version_id
     WHERE fr.id=NEW.release_id;

    IF release_mix IS NULL OR NEW.canonical_asset_id IS DISTINCT FROM expected_final_asset THEN
        RAISE EXCEPTION 'Narration release input must be the exact approved final-mix asset';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER final_release_narration_mix_asset_valid
BEFORE INSERT ON football_brief.final_release_inputs
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_final_release_narration_mix_asset();

COMMENT ON COLUMN football_brief.final_releases.audio_mix_version_id IS
    'Exact current approved P90 audio mix used by the P87 assembly job and sealed release manifest.';

COMMIT;
