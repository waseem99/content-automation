-- Football Brief P1: human review request and approval service
-- Depends on migrations/0001 through 0013

BEGIN;

CREATE TABLE football_brief.human_review_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    target_type text NOT NULL CHECK (target_type IN (
        'rights_gate', 'script', 'render_manifest', 'quality_report', 'stage', 'workflow', 'compliance'
    )),
    target_id uuid,
    review_type text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'decided', 'superseded', 'cancelled')),
    assigned_to text,
    requested_by text NOT NULL,
    reason text NOT NULL,
    prevent_self_approval boolean NOT NULL DEFAULT true,
    required_checklist jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz
);

CREATE INDEX human_review_requests_workflow_idx
    ON football_brief.human_review_requests (workflow_run_id, created_at DESC);
CREATE INDEX human_review_requests_stage_idx
    ON football_brief.human_review_requests (stage_execution_id, created_at DESC)
    WHERE stage_execution_id IS NOT NULL;
CREATE INDEX human_review_requests_target_idx
    ON football_brief.human_review_requests (target_type, target_id, created_at DESC)
    WHERE target_id IS NOT NULL;

ALTER TABLE football_brief.human_reviews
    ADD COLUMN IF NOT EXISTS review_request_id uuid REFERENCES football_brief.human_review_requests(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS target_type text CHECK (target_type IS NULL OR target_type IN (
        'rights_gate', 'script', 'render_manifest', 'quality_report', 'stage', 'workflow', 'compliance'
    )),
    ADD COLUMN IF NOT EXISTS target_id uuid,
    ADD COLUMN IF NOT EXISTS supersedes_review_id uuid REFERENCES football_brief.human_reviews(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS disclosure_texts jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS human_reviews_request_idx
    ON football_brief.human_reviews (review_request_id, created_at DESC)
    WHERE review_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS human_reviews_target_idx
    ON football_brief.human_reviews (target_type, target_id, created_at DESC)
    WHERE target_id IS NOT NULL;

CREATE OR REPLACE FUNCTION football_brief.validate_human_review_request()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF btrim(NEW.reason) = '' THEN
        RAISE EXCEPTION 'Review request reason is required';
    END IF;
    IF NEW.stage_execution_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM football_brief.stage_executions stage
        WHERE stage.id = NEW.stage_execution_id
          AND stage.workflow_run_id = NEW.workflow_run_id
    ) THEN
        RAISE EXCEPTION 'Review request stage must belong to workflow';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER human_review_requests_contract_guard
BEFORE INSERT ON football_brief.human_review_requests
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_human_review_request();

CREATE OR REPLACE FUNCTION football_brief.validate_human_review_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    req football_brief.human_review_requests%ROWTYPE;
BEGIN
    IF btrim(NEW.reviewer) = '' THEN
        RAISE EXCEPTION 'Reviewer identity is required';
    END IF;
    IF btrim(NEW.rationale) = '' THEN
        RAISE EXCEPTION 'Review rationale is required';
    END IF;
    IF NEW.checklist = '{}'::jsonb THEN
        RAISE EXCEPTION 'Review checklist is required';
    END IF;
    IF NEW.decision = 'pass_with_disclosure'
       AND jsonb_array_length(NEW.disclosure_texts) = 0 THEN
        RAISE EXCEPTION 'Disclosure decision requires disclosure text';
    END IF;

    IF NEW.review_request_id IS NOT NULL THEN
        SELECT * INTO req
        FROM football_brief.human_review_requests
        WHERE id = NEW.review_request_id;

        IF req.id IS NULL THEN
            RAISE EXCEPTION 'Review request does not exist';
        END IF;
        IF req.status <> 'open' THEN
            RAISE EXCEPTION 'Review request is not open';
        END IF;
        IF req.workflow_run_id IS DISTINCT FROM NEW.workflow_run_id
           OR req.stage_execution_id IS DISTINCT FROM NEW.stage_execution_id THEN
            RAISE EXCEPTION 'Review decision does not match review request';
        END IF;
        IF req.prevent_self_approval AND req.requested_by = NEW.reviewer THEN
            RAISE EXCEPTION 'Self approval is not allowed';
        END IF;
        NEW.target_type := COALESCE(NEW.target_type, req.target_type);
        NEW.target_id := COALESCE(NEW.target_id, req.target_id);
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER human_reviews_decision_contract_guard
BEFORE INSERT ON football_brief.human_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_human_review_decision();

CREATE OR REPLACE FUNCTION football_brief.close_human_review_request_after_decision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.review_request_id IS NOT NULL THEN
        UPDATE football_brief.human_review_requests
        SET status = 'decided', decided_at = NEW.created_at
        WHERE id = NEW.review_request_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER human_reviews_close_request
AFTER INSERT ON football_brief.human_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.close_human_review_request_after_decision();

CREATE OR REPLACE FUNCTION football_brief.reject_human_review_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Human review decisions are append-only';
END;
$$;

CREATE TRIGGER human_reviews_append_only
BEFORE UPDATE OR DELETE ON football_brief.human_reviews
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_human_review_mutation();

COMMENT ON TABLE football_brief.human_review_requests IS
    'Open review gates awaiting operator decision for stages, manifests, rights, quality, scripts or compliance targets.';
COMMENT ON TABLE football_brief.human_reviews IS
    'Append-only human review decisions with rationale, checklist, reviewer identity and optional disclosure text.';

COMMIT;
