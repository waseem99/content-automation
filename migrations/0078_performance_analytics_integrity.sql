-- Fail-closed observation lineage, exact economics, controlled experiments, and immutable evidence.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.reject_performance_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Performance analytics evidence is append-only';
END;
$$;

CREATE TRIGGER performance_import_batches_immutable
BEFORE UPDATE OR DELETE ON football_brief.performance_import_batches
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_performance_append_only_mutation();

CREATE TRIGGER performance_observations_immutable
BEFORE UPDATE OR DELETE ON football_brief.performance_observations
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_performance_append_only_mutation();

CREATE TRIGGER performance_experiment_results_immutable
BEFORE UPDATE OR DELETE ON football_brief.performance_experiment_results
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_performance_append_only_mutation();

CREATE TRIGGER performance_recommendations_immutable
BEFORE UPDATE OR DELETE ON football_brief.performance_recommendations
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_performance_append_only_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_import_batch()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    importer_active integer;
BEGIN
    SELECT count(*) INTO importer_active
      FROM football_brief.operator_users
     WHERE operator_id=NEW.imported_by AND active=true;
    IF importer_active<>1 THEN
        RAISE EXCEPTION 'Performance imports require an active operator';
    END IF;
    IF NEW.source_account_ref ~* '(password|secret|token|api[_-]?key)=' THEN
        RAISE EXCEPTION 'Performance import account references cannot contain secret material';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER performance_import_batches_valid
BEFORE INSERT ON football_brief.performance_import_batches
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_import_batch();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_observation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    batch_row football_brief.performance_import_batches%ROWTYPE;
    delivery_row football_brief.platform_delivery_requests%ROWTYPE;
    release_row football_brief.final_releases%ROWTYPE;
    content_brand uuid;
    routed_actual numeric(18,6);
    exact_cost numeric(18,6);
BEGIN
    SELECT * INTO batch_row
      FROM football_brief.performance_import_batches
     WHERE id=NEW.import_batch_id;
    SELECT * INTO delivery_row
      FROM football_brief.platform_delivery_requests
     WHERE id=NEW.delivery_request_id;
    SELECT * INTO release_row
      FROM football_brief.final_releases
     WHERE id=NEW.final_release_id;
    SELECT mp.brand_id INTO content_brand
      FROM football_brief.portfolio_content pc
      JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
     WHERE pc.id=NEW.portfolio_content_id AND pc.version=NEW.content_version;
    SELECT COALESCE(sum(psr.actual_amount),0) INTO routed_actual
      FROM football_brief.production_spend_reservations psr
     WHERE release_row.routing_plan_id IS NOT NULL
       AND psr.routing_plan_id=release_row.routing_plan_id
       AND psr.status='reconciled';
    exact_cost:=round(COALESCE(release_row.total_cost_usd,0)+COALESCE(routed_actual,0),6);

    IF batch_row.id IS NULL
       OR batch_row.brand_id IS DISTINCT FROM NEW.brand_id
       OR lower(batch_row.platform) IS DISTINCT FROM lower(NEW.platform)
       OR NEW.observed_at<batch_row.observed_from
       OR NEW.observed_at>batch_row.observed_to THEN
        RAISE EXCEPTION 'Observation must belong to the exact import batch brand, platform, and window';
    END IF;
    IF delivery_row.id IS NULL
       OR delivery_row.status<>'succeeded'
       OR delivery_row.final_release_id IS DISTINCT FROM NEW.final_release_id
       OR delivery_row.platform_reference IS DISTINCT FROM NEW.post_reference THEN
        RAISE EXCEPTION 'Observation requires the exact succeeded platform delivery reference';
    END IF;
    IF release_row.id IS NULL
       OR release_row.status<>'approved'
       OR release_row.portfolio_content_id IS DISTINCT FROM NEW.portfolio_content_id
       OR release_row.content_version IS DISTINCT FROM NEW.content_version
       OR content_brand IS DISTINCT FROM NEW.brand_id THEN
        RAISE EXCEPTION 'Observation requires exact approved release, content version, and brand lineage';
    END IF;
    IF NEW.production_cost_usd IS DISTINCT FROM exact_cost THEN
        RAISE EXCEPTION 'Observation production cost must equal release cost plus reconciled managed spend';
    END IF;
    IF NOT (
        NEW.creative_snapshot ? 'concept'
        AND NEW.creative_snapshot ? 'pillar'
        AND NEW.creative_snapshot ? 'hook'
        AND NEW.creative_snapshot ? 'duration_seconds'
        AND NEW.creative_snapshot ? 'narration_preset_id'
        AND NEW.creative_snapshot ? 'visual_style'
        AND NEW.creative_snapshot ? 'renderers'
        AND NEW.creative_snapshot ? 'format'
        AND jsonb_typeof(NEW.creative_snapshot->'renderers')='array'
    ) THEN
        RAISE EXCEPTION 'Observation creative snapshot must cite concept, pillar, hook, duration, narration, visual style, renderers, and format';
    END IF;
    IF NEW.normalized_views>NEW.views THEN
        RAISE EXCEPTION 'Normalized views cannot exceed source views';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER performance_observations_valid
BEFORE INSERT ON football_brief.performance_observations
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_observation();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_experiment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.performance_experiments%ROWTYPE;
    variant_total integer;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Performance experiments cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.version>1 THEN
            SELECT * INTO parent_row
              FROM football_brief.performance_experiments
             WHERE id=NEW.parent_experiment_id;
            IF parent_row.id IS NULL
               OR parent_row.brand_id IS DISTINCT FROM NEW.brand_id
               OR parent_row.experiment_key IS DISTINCT FROM NEW.experiment_key
               OR parent_row.version+1<>NEW.version
               OR parent_row.status<>'superseded' THEN
                RAISE EXCEPTION 'Experiment revisions require the immediately superseded parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.brand_id IS DISTINCT FROM OLD.brand_id
       OR NEW.experiment_key IS DISTINCT FROM OLD.experiment_key
       OR NEW.display_name IS DISTINCT FROM OLD.display_name
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_experiment_id IS DISTINCT FROM OLD.parent_experiment_id
       OR NEW.hypothesis IS DISTINCT FROM OLD.hypothesis
       OR NEW.winner_criteria IS DISTINCT FROM OLD.winner_criteria
       OR NEW.minimum_observation_count IS DISTINCT FROM OLD.minimum_observation_count
       OR NEW.minimum_views_per_variant IS DISTINCT FROM OLD.minimum_views_per_variant
       OR NEW.significance_threshold IS DISTINCT FROM OLD.significance_threshold
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Performance experiment configuration is immutable';
    END IF;
    IF OLD.status IN ('completed','cancelled','superseded') THEN
        RAISE EXCEPTION 'Terminal performance experiments are immutable';
    END IF;
    IF OLD.status='draft' AND NEW.status='active' THEN
        SELECT count(*) INTO variant_total
          FROM football_brief.performance_experiment_variants
         WHERE experiment_id=OLD.id;
        IF variant_total<2 OR NEW.activated_at IS NULL THEN
            RAISE EXCEPTION 'Experiment activation requires at least two declared variants and activation evidence';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status='active' AND NEW.status='completed' AND NEW.completed_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('draft','active') AND NEW.status='cancelled' AND NEW.cancelled_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status='active' AND NEW.status='superseded' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid performance experiment transition';
END;
$$;

CREATE TRIGGER performance_experiments_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.performance_experiments
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_experiment();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_experiment_variant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    experiment_row football_brief.performance_experiments%ROWTYPE;
    release_row football_brief.final_releases%ROWTYPE;
    delivery_row football_brief.platform_delivery_requests%ROWTYPE;
    release_brand uuid;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'Experiment variants are immutable';
    END IF;
    SELECT * INTO experiment_row
      FROM football_brief.performance_experiments
     WHERE id=NEW.experiment_id;
    SELECT * INTO release_row
      FROM football_brief.final_releases
     WHERE id=NEW.final_release_id;
    SELECT * INTO delivery_row
      FROM football_brief.platform_delivery_requests
     WHERE id=NEW.delivery_request_id;
    SELECT mp.brand_id INTO release_brand
      FROM football_brief.portfolio_content pc
      JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
     WHERE pc.id=release_row.portfolio_content_id;
    IF experiment_row.id IS NULL OR experiment_row.status<>'draft'
       OR release_row.id IS NULL OR release_row.status<>'approved'
       OR delivery_row.id IS NULL OR delivery_row.status<>'succeeded'
       OR delivery_row.final_release_id IS DISTINCT FROM release_row.id
       OR release_brand IS DISTINCT FROM experiment_row.brand_id THEN
        RAISE EXCEPTION 'Experiment variants require draft experiment and exact successful delivered release for the same brand';
    END IF;
    IF NEW.declared_changes='{}'::jsonb THEN
        RAISE EXCEPTION 'Experiment variants require declared creative changes';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER performance_experiment_variants_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.performance_experiment_variants
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_experiment_variant();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_experiment_result()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    experiment_row football_brief.performance_experiments%ROWTYPE;
    evidence_total integer;
    evidence_match integer;
    wrong_experiment integer;
    winner_match integer;
BEGIN
    SELECT * INTO experiment_row
      FROM football_brief.performance_experiments
     WHERE id=NEW.experiment_id;
    evidence_total:=cardinality(NEW.evaluated_observation_ids);
    SELECT count(DISTINCT po.id),
           count(*) FILTER (WHERE po.id IS NOT NULL AND pev.id IS NULL)
      INTO evidence_match,wrong_experiment
      FROM unnest(NEW.evaluated_observation_ids) evidence_id
      LEFT JOIN football_brief.performance_observations po ON po.id=evidence_id
      LEFT JOIN football_brief.performance_experiment_variants pev
        ON pev.experiment_id=NEW.experiment_id
       AND pev.delivery_request_id=po.delivery_request_id;
    SELECT count(*) INTO winner_match
      FROM football_brief.performance_experiment_variants pev
     WHERE pev.id=NEW.winner_variant_id AND pev.experiment_id=NEW.experiment_id;
    IF experiment_row.id IS NULL OR experiment_row.status NOT IN ('active','completed') THEN
        RAISE EXCEPTION 'Experiment results require an active or completed experiment';
    END IF;
    IF evidence_total<>evidence_match OR wrong_experiment<>0 THEN
        RAISE EXCEPTION 'Experiment results must cite unique observations from declared experiment variants';
    END IF;
    IF NEW.result_status='meaningful_result' AND winner_match<>1 THEN
        RAISE EXCEPTION 'Meaningful experiment result winner must belong to the experiment';
    END IF;
    IF NOT (NEW.criteria_snapshot ? 'metric' AND NEW.criteria_snapshot ? 'direction')
       OR NEW.metric_summary='{}'::jsonb THEN
        RAISE EXCEPTION 'Experiment result must retain winner criteria and metric summary evidence';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER performance_experiment_results_valid
BEFORE INSERT ON football_brief.performance_experiment_results
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_experiment_result();

CREATE OR REPLACE FUNCTION football_brief.validate_performance_recommendation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    evidence_total integer;
    evidence_match integer;
    wrong_brand integer;
    result_wrong_brand integer;
BEGIN
    evidence_total:=cardinality(NEW.cited_observation_ids);
    SELECT count(DISTINCT po.id),
           count(*) FILTER (WHERE po.id IS NOT NULL AND po.brand_id IS DISTINCT FROM NEW.brand_id)
      INTO evidence_match,wrong_brand
      FROM unnest(NEW.cited_observation_ids) evidence_id
      LEFT JOIN football_brief.performance_observations po ON po.id=evidence_id;
    SELECT count(*) INTO result_wrong_brand
      FROM football_brief.performance_experiment_results per
      JOIN football_brief.performance_experiments pe ON pe.id=per.experiment_id
     WHERE per.id=NEW.experiment_result_id
       AND pe.brand_id IS DISTINCT FROM NEW.brand_id;
    IF evidence_total<>evidence_match OR wrong_brand<>0 OR result_wrong_brand<>0 THEN
        RAISE EXCEPTION 'Performance recommendations must cite existing observations and results for the same brand';
    END IF;
    IF jsonb_array_length(NEW.metric_citations)=0 THEN
        RAISE EXCEPTION 'Performance recommendations require metric citations';
    END IF;
    IF NEW.recommendation ~* '(auto[- ]?(approve|publish|deliver)|without review)' THEN
        RAISE EXCEPTION 'Performance recommendations cannot authorize automatic approval or delivery';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER performance_recommendations_valid
BEFORE INSERT ON football_brief.performance_recommendations
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_performance_recommendation();

COMMIT;
