-- Football Brief Phase 0: publish-mode quality gate and compliance report enforcement
-- Depends on migrations/0001 through 0011

BEGIN;

ALTER TABLE football_brief.quality_reports
    ADD COLUMN IF NOT EXISTS render_manifest_id uuid REFERENCES football_brief.render_manifests(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS output_asset_id uuid REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS check_registry_version text NOT NULL DEFAULT 'quality-gate-v1',
    ADD COLUMN IF NOT EXISTS input_hash char(64),
    ADD COLUMN IF NOT EXISTS output_hash char(64),
    ADD COLUMN IF NOT EXISTS report_hash char(64),
    ADD COLUMN IF NOT EXISTS disclosure_texts jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS human_review_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS quality_reports_report_hash_idx
    ON football_brief.quality_reports (report_hash)
    WHERE report_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS quality_reports_manifest_idx
    ON football_brief.quality_reports (render_manifest_id, created_at DESC)
    WHERE render_manifest_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS quality_reports_output_asset_idx
    ON football_brief.quality_reports (output_asset_id, created_at DESC)
    WHERE output_asset_id IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.validate_quality_report_contract()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    job football_brief.render_jobs%ROWTYPE;
    manifest football_brief.render_manifests%ROWTYPE;
    output_asset football_brief.assets%ROWTYPE;
BEGIN
    SELECT * INTO job FROM football_brief.render_jobs WHERE id = NEW.render_job_id;
    IF job.id IS NULL THEN
        RAISE EXCEPTION 'Quality report render job does not exist';
    END IF;

    SELECT * INTO manifest FROM football_brief.render_manifests WHERE id = job.render_manifest_id;
    IF manifest.id IS NULL THEN
        RAISE EXCEPTION 'Quality report manifest does not exist';
    END IF;

    IF NEW.render_manifest_id IS NULL THEN
        NEW.render_manifest_id := job.render_manifest_id;
    ELSIF NEW.render_manifest_id IS DISTINCT FROM job.render_manifest_id THEN
        RAISE EXCEPTION 'Quality report manifest does not match render job';
    END IF;

    IF NEW.output_asset_id IS NULL THEN
        NEW.output_asset_id := job.output_asset_id;
    ELSIF NEW.output_asset_id IS DISTINCT FROM job.output_asset_id THEN
        RAISE EXCEPTION 'Quality report output asset does not match render job';
    END IF;

    IF NEW.output_asset_id IS NOT NULL THEN
        SELECT * INTO output_asset FROM football_brief.assets WHERE id = NEW.output_asset_id;
        IF output_asset.id IS NULL THEN
            RAISE EXCEPTION 'Quality report output asset does not exist';
        END IF;
        IF NEW.output_hash IS NOT NULL AND output_asset.sha256 IS DISTINCT FROM NEW.output_hash THEN
            RAISE EXCEPTION 'Quality report output hash does not match asset';
        END IF;
    END IF;

    IF NEW.overall_status = 'pass_with_disclosure'
       AND jsonb_array_length(NEW.disclosure_texts) = 0 THEN
        RAISE EXCEPTION 'PASS_WITH_DISCLOSURE requires disclosure text';
    END IF;

    IF NEW.overall_status = 'human_review_required'
       AND jsonb_array_length(NEW.human_review_reasons) = 0 THEN
        RAISE EXCEPTION 'HUMAN_REVIEW_REQUIRED requires human review reasons';
    END IF;

    IF NEW.overall_status = 'block'
       AND jsonb_array_length(NEW.blocking_failures) = 0 THEN
        RAISE EXCEPTION 'BLOCK quality reports require blocking failures';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER quality_reports_contract_guard
BEFORE INSERT ON football_brief.quality_reports
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_quality_report_contract();

ALTER TABLE football_brief.publication_packages
    ADD COLUMN IF NOT EXISTS quality_report_id uuid REFERENCES football_brief.quality_reports(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS publication_packages_quality_report_idx
    ON football_brief.publication_packages (quality_report_id)
    WHERE quality_report_id IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.require_quality_report_for_publication_package()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    job football_brief.render_jobs%ROWTYPE;
    manifest football_brief.render_manifests%ROWTYPE;
    report football_brief.quality_reports%ROWTYPE;
BEGIN
    SELECT * INTO job FROM football_brief.render_jobs WHERE id = NEW.render_job_id;
    IF job.id IS NULL THEN
        RAISE EXCEPTION 'Publication package render job does not exist';
    END IF;

    SELECT * INTO manifest FROM football_brief.render_manifests WHERE id = NEW.render_manifest_id;
    IF manifest.id IS NULL THEN
        RAISE EXCEPTION 'Publication package manifest does not exist';
    END IF;

    IF job.render_manifest_id IS DISTINCT FROM NEW.render_manifest_id THEN
        RAISE EXCEPTION 'Publication package manifest does not match render job';
    END IF;

    IF manifest.mode <> 'publish' THEN
        RAISE EXCEPTION 'Publication packages require publish manifests';
    END IF;

    IF job.status <> 'succeeded' OR job.output_asset_id IS NULL THEN
        RAISE EXCEPTION 'Publication packages require a succeeded render job with output asset';
    END IF;

    IF NEW.quality_report_id IS NULL THEN
        SELECT * INTO report
        FROM football_brief.quality_reports
        WHERE render_job_id = NEW.render_job_id
        ORDER BY created_at DESC
        LIMIT 1;
        NEW.quality_report_id := report.id;
    ELSE
        SELECT * INTO report FROM football_brief.quality_reports WHERE id = NEW.quality_report_id;
    END IF;

    IF report.id IS NULL THEN
        RAISE EXCEPTION 'Publication packages require a quality report';
    END IF;

    IF report.render_job_id IS DISTINCT FROM NEW.render_job_id
       OR report.render_manifest_id IS DISTINCT FROM NEW.render_manifest_id
       OR report.output_asset_id IS DISTINCT FROM job.output_asset_id THEN
        RAISE EXCEPTION 'Publication package quality report does not match render output';
    END IF;

    IF report.overall_status NOT IN ('pass', 'pass_with_disclosure') THEN
        RAISE EXCEPTION 'Publication packages require a passing quality report';
    END IF;

    IF report.overall_status = 'pass_with_disclosure'
       AND jsonb_array_length(report.disclosure_texts) = 0 THEN
        RAISE EXCEPTION 'Publication package disclosure report lacks required text';
    END IF;

    NEW.metadata := COALESCE(NEW.metadata, '{}'::jsonb)
        || jsonb_build_object(
            'quality_report_id', report.id,
            'quality_status', report.overall_status,
            'disclosure_texts', report.disclosure_texts
        );

    RETURN NEW;
END;
$$;

CREATE TRIGGER publication_package_quality_gate
BEFORE INSERT ON football_brief.publication_packages
FOR EACH ROW EXECUTE FUNCTION football_brief.require_quality_report_for_publication_package();

COMMENT ON TABLE football_brief.quality_reports IS
    'Structured publish-readiness and media quality reports. A succeeded render is not equivalent to publication approval.';
COMMENT ON COLUMN football_brief.publication_packages.quality_report_id IS
    'Latest applicable passing quality report that permitted publication packaging.';

COMMIT;
