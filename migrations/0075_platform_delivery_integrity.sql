-- Fail-closed target versioning, publisher queue access, request transitions, and attempt evidence.

BEGIN;

CREATE OR REPLACE FUNCTION football_brief.reject_platform_delivery_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Platform delivery event evidence is append-only';
END;
$$;

CREATE TRIGGER platform_delivery_events_immutable
BEFORE UPDATE OR DELETE ON football_brief.platform_delivery_events
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_platform_delivery_append_only_mutation();

CREATE OR REPLACE FUNCTION football_brief.validate_platform_delivery_target()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_row football_brief.platform_delivery_targets%ROWTYPE;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Platform delivery targets cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.version>1 THEN
            SELECT * INTO parent_row
              FROM football_brief.platform_delivery_targets
             WHERE id=NEW.parent_target_id;
            IF parent_row.id IS NULL
               OR parent_row.target_key IS DISTINCT FROM NEW.target_key
               OR parent_row.version+1<>NEW.version
               OR parent_row.status<>'retired' THEN
                RAISE EXCEPTION 'Delivery target revisions require the immediately retired parent';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='retired' THEN
        RAISE EXCEPTION 'Retired platform delivery targets are immutable';
    END IF;
    IF NEW.target_key IS DISTINCT FROM OLD.target_key
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.parent_target_id IS DISTINCT FROM OLD.parent_target_id
       OR NEW.display_name IS DISTINCT FROM OLD.display_name
       OR NEW.platform IS DISTINCT FROM OLD.platform
       OR NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.primary_adapter_key IS DISTINCT FROM OLD.primary_adapter_key
       OR NEW.fallback_adapter_key IS DISTINCT FROM OLD.fallback_adapter_key
       OR NEW.supported_privacy IS DISTINCT FROM OLD.supported_privacy
       OR NEW.default_privacy IS DISTINCT FROM OLD.default_privacy
       OR NEW.credential_secret_ref IS DISTINCT FROM OLD.credential_secret_ref
       OR NEW.simulated IS DISTINCT FROM OLD.simulated
       OR NEW.execution_enabled IS DISTINCT FROM OLD.execution_enabled
       OR NEW.requests_per_minute IS DISTINCT FROM OLD.requests_per_minute
       OR NEW.requests_per_day IS DISTINCT FROM OLD.requests_per_day
       OR NEW.configuration IS DISTINCT FROM OLD.configuration
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Platform delivery target configuration is immutable';
    END IF;

    IF OLD.status='draft' AND NEW.status='active'
       AND NEW.activated_by IS NOT NULL AND NEW.activated_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status='active' AND NEW.status='unavailable' THEN
        RETURN NEW;
    END IF;
    IF OLD.status='unavailable' AND NEW.status='active'
       AND NEW.activated_by IS NOT NULL AND NEW.activated_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IN ('draft','active','unavailable') AND NEW.status='retired'
       AND NEW.retired_by IS NOT NULL AND NEW.retired_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid platform delivery target transition';
END;
$$;

CREATE TRIGGER platform_delivery_targets_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.platform_delivery_targets
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_platform_delivery_target();

CREATE OR REPLACE FUNCTION football_brief.validate_platform_delivery_request()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_row football_brief.final_releases%ROWTYPE;
    target_row football_brief.platform_delivery_targets%ROWTYPE;
    output_available integer;
    publisher_count integer;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Platform delivery requests cannot be deleted';
    END IF;

    IF TG_OP='INSERT' THEN
        SELECT * INTO release_row
          FROM football_brief.final_releases
         WHERE id=NEW.final_release_id;
        SELECT * INTO target_row
          FROM football_brief.platform_delivery_targets
         WHERE id=NEW.target_id;
        SELECT count(*) INTO output_available
          FROM football_brief.shared_artifact_object_roles saor
          JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
         WHERE saor.artifact_version_id=release_row.output_artifact_version_id
           AND saor.role='original'
           AND sso.status='available';
        SELECT count(*) INTO publisher_count
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.created_by
           AND ou.active=true
           AND our.role='publisher';

        IF release_row.id IS NULL
           OR release_row.status<>'approved'
           OR release_row.manifest_hash IS DISTINCT FROM NEW.release_manifest_hash
           OR release_row.release_manifest IS NULL
           OR output_available<>1 THEN
            RAISE EXCEPTION 'Delivery requires the exact approved release manifest and available output';
        END IF;
        IF target_row.id IS NULL
           OR target_row.status<>'active'
           OR target_row.execution_enabled=false
           OR target_row.simulated=false
           OR NOT (NEW.privacy=ANY(target_row.supported_privacy)) THEN
            RAISE EXCEPTION 'Delivery requires an active executable simulated target supporting the privacy mode';
        END IF;
        IF publisher_count<>1 THEN
            RAISE EXCEPTION 'Only an active Publisher can create a delivery request';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('succeeded','failed','cancelled') THEN
        RAISE EXCEPTION 'Terminal platform delivery requests are immutable';
    END IF;
    IF NEW.final_release_id IS DISTINCT FROM OLD.final_release_id
       OR NEW.target_id IS DISTINCT FROM OLD.target_id
       OR NEW.release_manifest_hash IS DISTINCT FROM OLD.release_manifest_hash
       OR NEW.delivery_fingerprint IS DISTINCT FROM OLD.delivery_fingerprint
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.privacy IS DISTINCT FROM OLD.privacy
       OR NEW.scheduled_for IS DISTINCT FROM OLD.scheduled_for
       OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Platform delivery request identity is immutable';
    END IF;

    IF OLD.status IN ('queued','retry_wait') AND NEW.status=OLD.status THEN
        IF NEW.attempt_count IS DISTINCT FROM OLD.attempt_count
           OR NEW.current_worker_id IS DISTINCT FROM OLD.current_worker_id
           OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
           OR NEW.lease_expires_at IS DISTINCT FROM OLD.lease_expires_at
           OR NEW.platform_reference IS DISTINCT FROM OLD.platform_reference
           OR NEW.started_at IS DISTINCT FROM OLD.started_at
           OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
           OR NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at
           OR NEW.cancelled_by IS DISTINCT FROM OLD.cancelled_by
           OR NEW.last_error_code IS DISTINCT FROM OLD.last_error_code
           OR NEW.last_error_message IS DISTINCT FROM OLD.last_error_message
           OR NEW.last_error_retryable IS DISTINCT FROM OLD.last_error_retryable
           OR NEW.next_attempt_at<OLD.next_attempt_at THEN
            RAISE EXCEPTION 'Queued delivery deferral may only move next_attempt_at forward';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('queued','retry_wait') AND NEW.status='processing' THEN
        SELECT * INTO release_row
          FROM football_brief.final_releases
         WHERE id=OLD.final_release_id;
        SELECT * INTO target_row
          FROM football_brief.platform_delivery_targets
         WHERE id=OLD.target_id;
        SELECT count(*) INTO publisher_count
          FROM football_brief.operator_users ou
          JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
         WHERE ou.operator_id=NEW.current_worker_id
           AND ou.active=true
           AND our.role='publisher';
        IF release_row.status<>'approved'
           OR release_row.manifest_hash IS DISTINCT FROM OLD.release_manifest_hash
           OR target_row.status<>'active'
           OR target_row.execution_enabled=false
           OR target_row.simulated=false
           OR publisher_count<>1
           OR NEW.attempt_count<>OLD.attempt_count+1
           OR NEW.lease_token IS NULL
           OR NEW.lease_expires_at IS NULL
           OR NEW.current_worker_id IS NULL THEN
            RAISE EXCEPTION 'Delivery claim requires the current approved release, executable target, and active Publisher lease';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='processing' AND NEW.status='succeeded' THEN
        IF NEW.platform_reference IS NULL OR NEW.completed_at IS NULL
           OR NEW.current_worker_id IS NOT NULL OR NEW.lease_token IS NOT NULL
           OR NEW.lease_expires_at IS NOT NULL THEN
            RAISE EXCEPTION 'Successful delivery requires a platform reference and cleared lease';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='processing' AND NEW.status='retry_wait' THEN
        IF NEW.last_error_code IS NULL OR NEW.last_error_message IS NULL
           OR NEW.last_error_retryable IS DISTINCT FROM true
           OR NEW.next_attempt_at<=now()
           OR NEW.current_worker_id IS NOT NULL OR NEW.lease_token IS NOT NULL
           OR NEW.lease_expires_at IS NOT NULL THEN
            RAISE EXCEPTION 'Retryable delivery failure requires retained error evidence and a future retry';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status='processing' AND NEW.status='failed' THEN
        IF NEW.last_error_code IS NULL OR NEW.last_error_message IS NULL
           OR NEW.completed_at IS NULL
           OR NEW.current_worker_id IS NOT NULL OR NEW.lease_token IS NOT NULL
           OR NEW.lease_expires_at IS NOT NULL THEN
            RAISE EXCEPTION 'Terminal delivery failure requires retained error evidence and a cleared lease';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('queued','retry_wait') AND NEW.status='cancelled' THEN
        IF NEW.cancelled_at IS NULL OR NEW.cancelled_by IS NULL THEN
            RAISE EXCEPTION 'Delivery cancellation requires actor and timestamp evidence';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Invalid platform delivery request transition from % to %',OLD.status,NEW.status;
END;
$$;

CREATE TRIGGER platform_delivery_requests_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.platform_delivery_requests
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_platform_delivery_request();

CREATE OR REPLACE FUNCTION football_brief.validate_platform_delivery_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Platform delivery attempts cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.status<>'running' THEN
            RAISE EXCEPTION 'Platform delivery attempts must begin in running state';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status<>'running' THEN
        RAISE EXCEPTION 'Terminal platform delivery attempts are immutable';
    END IF;
    IF NEW.delivery_request_id IS DISTINCT FROM OLD.delivery_request_id
       OR NEW.sequence_number IS DISTINCT FROM OLD.sequence_number
       OR NEW.cycle_number IS DISTINCT FROM OLD.cycle_number
       OR NEW.transport IS DISTINCT FROM OLD.transport
       OR NEW.adapter_key IS DISTINCT FROM OLD.adapter_key
       OR NEW.request_snapshot IS DISTINCT FROM OLD.request_snapshot
       OR NEW.worker_id IS DISTINCT FROM OLD.worker_id
       OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'Platform delivery attempt identity and request snapshot are immutable';
    END IF;
    IF NEW.status='succeeded'
       AND NEW.finished_at IS NOT NULL
       AND NEW.response_payload IS NOT NULL
       AND NEW.provider_request_id IS NOT NULL
       AND NEW.platform_reference IS NOT NULL
       AND NEW.error_code IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.status='failed'
       AND NEW.finished_at IS NOT NULL
       AND NEW.error_code IS NOT NULL
       AND NEW.error_message IS NOT NULL
       AND NEW.retryable IS NOT NULL
       AND NEW.response_payload IS NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid platform delivery attempt transition';
END;
$$;

CREATE TRIGGER platform_delivery_attempts_valid
BEFORE INSERT OR UPDATE OR DELETE ON football_brief.platform_delivery_attempts
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_platform_delivery_attempt();

COMMIT;
