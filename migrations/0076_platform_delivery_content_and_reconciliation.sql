-- Structured delivery copy, thumbnail lineage, target-account contracts, and reconciliation evidence.

BEGIN;

ALTER TABLE football_brief.platform_delivery_targets
    ADD CONSTRAINT platform_delivery_target_content_contract CHECK (
        configuration ? 'target_account_ref'
        AND length(btrim(configuration->>'target_account_ref')) BETWEEN 3 AND 240
        AND configuration ? 'time_zone'
        AND length(btrim(configuration->>'time_zone')) BETWEEN 1 AND 100
        AND jsonb_typeof(configuration->'content_contract')='object'
        AND (configuration->'content_contract' ? 'title_max_length')
        AND (configuration->'content_contract' ? 'caption_max_length')
        AND (configuration->'content_contract' ? 'hashtag_limit')
        AND (configuration->'content_contract' ? 'thumbnail_required')
        AND (configuration->'content_contract' ? 'disclosure_required')
        AND (configuration->'content_contract'->>'title_max_length')::integer BETWEEN 1 AND 1000
        AND (configuration->'content_contract'->>'caption_max_length')::integer BETWEEN 1 AND 20000
        AND (configuration->'content_contract'->>'hashtag_limit')::integer BETWEEN 0 AND 100
        AND jsonb_typeof(configuration->'content_contract'->'thumbnail_required')='boolean'
        AND jsonb_typeof(configuration->'content_contract'->'disclosure_required')='boolean'
    );

ALTER TABLE football_brief.platform_delivery_requests
    ADD CONSTRAINT platform_delivery_request_content_snapshot CHECK (
        metadata ? 'delivery_mode'
        AND metadata->>'delivery_mode' IN ('draft','immediate','scheduled')
        AND metadata ? 'title'
        AND length(btrim(metadata->>'title')) BETWEEN 1 AND 1000
        AND metadata ? 'caption'
        AND length(btrim(metadata->>'caption')) BETWEEN 1 AND 20000
        AND metadata ? 'hashtags'
        AND jsonb_typeof(metadata->'hashtags')='array'
        AND jsonb_array_length(metadata->'hashtags')<=100
        AND metadata ? 'thumbnail_artifact_version_id'
        AND metadata ? 'disclosure_text'
    );

CREATE OR REPLACE FUNCTION football_brief.validate_platform_delivery_content()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    target_row football_brief.platform_delivery_targets%ROWTYPE;
    contract jsonb;
    mode_text text;
    title_text text;
    caption_text text;
    thumbnail_text text;
    disclosure_text text;
    thumbnail_available integer;
    target_brand uuid;
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.metadata IS DISTINCT FROM OLD.metadata THEN
            RAISE EXCEPTION 'Platform delivery content snapshot is immutable';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO release_row
      FROM football_brief.final_releases
     WHERE id=NEW.final_release_id;
    SELECT * INTO target_row
      FROM football_brief.platform_delivery_targets
     WHERE id=NEW.target_id;

    IF release_row.id IS NULL OR target_row.id IS NULL THEN
        RAISE EXCEPTION 'Delivery content requires an existing release and target';
    END IF;

    contract:=target_row.configuration->'content_contract';
    mode_text:=NEW.metadata->>'delivery_mode';
    title_text:=btrim(NEW.metadata->>'title');
    caption_text:=btrim(NEW.metadata->>'caption');
    thumbnail_text:=NULLIF(NEW.metadata->>'thumbnail_artifact_version_id','');
    disclosure_text:=NULLIF(btrim(NEW.metadata->>'disclosure_text'),'');

    IF mode_text='scheduled' AND NEW.scheduled_for<=now() THEN
        RAISE EXCEPTION 'Scheduled delivery requires a future time';
    END IF;
    IF mode_text IN ('draft','immediate') AND NEW.scheduled_for>now()+interval '5 minutes' THEN
        RAISE EXCEPTION 'Draft and immediate delivery cannot carry a future schedule';
    END IF;
    IF length(title_text)>(contract->>'title_max_length')::integer THEN
        RAISE EXCEPTION 'Delivery title exceeds the target limit';
    END IF;
    IF length(caption_text)>(contract->>'caption_max_length')::integer THEN
        RAISE EXCEPTION 'Delivery caption exceeds the target limit';
    END IF;
    IF jsonb_array_length(NEW.metadata->'hashtags')>(contract->>'hashtag_limit')::integer THEN
        RAISE EXCEPTION 'Delivery hashtags exceed the target limit';
    END IF;
    IF (contract->>'disclosure_required')::boolean AND disclosure_text IS NULL THEN
        RAISE EXCEPTION 'Delivery disclosure is required by the target';
    END IF;
    IF (contract->>'thumbnail_required')::boolean AND thumbnail_text IS NULL THEN
        RAISE EXCEPTION 'Delivery thumbnail is required by the target';
    END IF;

    IF thumbnail_text IS NOT NULL THEN
        IF thumbnail_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN
            RAISE EXCEPTION 'Delivery thumbnail identity is invalid';
        END IF;
        SELECT mp.brand_id INTO target_brand
          FROM football_brief.portfolio_content pc
          JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
         WHERE pc.id=release_row.portfolio_content_id;
        SELECT count(DISTINCT sav.id) INTO thumbnail_available
          FROM football_brief.shared_artifact_versions sav
          JOIN football_brief.shared_artifact_object_roles saor
            ON saor.artifact_version_id=sav.id
          JOIN football_brief.shared_storage_objects sso
            ON sso.id=saor.storage_object_id
         WHERE sav.id=thumbnail_text::uuid
           AND sav.brand_id=target_brand
           AND sav.portfolio_content_id=release_row.portfolio_content_id
           AND sav.content_version=release_row.content_version
           AND sav.artifact_kind='thumbnail'
           AND sav.status='current'
           AND saor.role IN ('original','thumbnail')
           AND sso.status='available';
        IF thumbnail_available<>1 THEN
            RAISE EXCEPTION 'Delivery thumbnail must be the exact current available thumbnail for the release';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER platform_delivery_content_valid
BEFORE INSERT OR UPDATE ON football_brief.platform_delivery_requests
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_platform_delivery_content();

CREATE TABLE football_brief.platform_delivery_reconciliations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_request_id uuid NOT NULL
        REFERENCES football_brief.platform_delivery_requests(id) ON DELETE RESTRICT,
    sequence_number integer NOT NULL CHECK (sequence_number>=1),
    adapter_key text NOT NULL CHECK (length(btrim(adapter_key)) BETWEEN 2 AND 120),
    platform_reference text NOT NULL CHECK (length(btrim(platform_reference)) BETWEEN 1 AND 2000),
    platform_status text NOT NULL CHECK (platform_status IN (
        'draft','scheduled','published','failed','deleted','unknown'
    )),
    response_payload jsonb NOT NULL CHECK (jsonb_typeof(response_payload)='object'),
    reconciled_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (delivery_request_id,sequence_number)
);

CREATE INDEX platform_delivery_reconciliation_request_idx
ON football_brief.platform_delivery_reconciliations(delivery_request_id,sequence_number DESC);

CREATE OR REPLACE FUNCTION football_brief.reject_platform_delivery_reconciliation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Platform delivery reconciliation evidence is append-only';
END;
$$;

CREATE TRIGGER platform_delivery_reconciliations_immutable
BEFORE UPDATE OR DELETE ON football_brief.platform_delivery_reconciliations
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_platform_delivery_reconciliation_mutation();

COMMENT ON TABLE football_brief.platform_delivery_reconciliations IS
    'Append-only simulated platform status observations for a terminal delivery reference.';

COMMIT;
