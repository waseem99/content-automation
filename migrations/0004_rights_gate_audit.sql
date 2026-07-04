-- Football Brief Phase 0: fail-closed rights authorization and audit evidence
-- Depends on migrations/0001, 0002, and 0003

BEGIN;

CREATE TABLE football_brief.asset_rights_evidence_links (
    asset_rights_id uuid NOT NULL
        REFERENCES football_brief.asset_rights(id) ON DELETE RESTRICT,
    rights_evidence_id uuid NOT NULL
        REFERENCES football_brief.rights_evidence(id) ON DELETE RESTRICT,
    evidence_role text NOT NULL DEFAULT 'supporting' CHECK (evidence_role IN (
        'supporting', 'license', 'contract', 'receipt', 'consent',
        'terms_snapshot', 'attribution'
    )),
    linked_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_rights_id, rights_evidence_id)
);

CREATE INDEX asset_rights_evidence_links_evidence_idx
    ON football_brief.asset_rights_evidence_links (rights_evidence_id);

CREATE OR REPLACE FUNCTION football_brief.validate_rights_evidence_asset_match()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    rights_asset_id uuid;
    evidence_target_asset_id uuid;
BEGIN
    SELECT asset_id INTO rights_asset_id
    FROM football_brief.asset_rights
    WHERE id = NEW.asset_rights_id;

    SELECT asset_id INTO evidence_target_asset_id
    FROM football_brief.rights_evidence
    WHERE id = NEW.rights_evidence_id;

    IF rights_asset_id IS NULL OR evidence_target_asset_id IS NULL THEN
        RAISE EXCEPTION 'Rights or evidence record does not exist';
    END IF;
    IF rights_asset_id <> evidence_target_asset_id THEN
        RAISE EXCEPTION 'Rights evidence must target the same asset as the rights record';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER asset_rights_evidence_asset_match
BEFORE INSERT OR UPDATE ON football_brief.asset_rights_evidence_links
FOR EACH ROW EXECUTE FUNCTION football_brief.validate_rights_evidence_asset_match();

CREATE OR REPLACE FUNCTION football_brief.require_evidence_for_approved_rights()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    target_rights_id uuid;
    current_status text;
BEGIN
    target_rights_id := COALESCE(NEW.id, OLD.asset_rights_id);
    SELECT approval_status INTO current_status
    FROM football_brief.asset_rights
    WHERE id = target_rights_id;

    IF current_status = 'approved' AND NOT EXISTS (
        SELECT 1
        FROM football_brief.asset_rights_evidence_links
        WHERE asset_rights_id = target_rights_id
    ) THEN
        RAISE EXCEPTION 'Approved rights require linked evidence';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE CONSTRAINT TRIGGER approved_rights_require_evidence
AFTER INSERT OR UPDATE OF approval_status ON football_brief.asset_rights
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION football_brief.require_evidence_for_approved_rights();

CREATE CONSTRAINT TRIGGER approved_rights_keep_evidence
AFTER DELETE ON football_brief.asset_rights_evidence_links
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION football_brief.require_evidence_for_approved_rights();

CREATE TABLE football_brief.rights_gate_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id uuid NOT NULL
        REFERENCES football_brief.workflow_runs(id) ON DELETE RESTRICT,
    stage_execution_id uuid
        REFERENCES football_brief.stage_executions(id) ON DELETE RESTRICT,
    gate_point text NOT NULL CHECK (gate_point IN (
        'manifest_admission', 'render_start', 'manual_check'
    )),
    platform text NOT NULL,
    territory text NOT NULL,
    campaign text,
    requested_uses text[] NOT NULL DEFAULT ARRAY[]::text[],
    policy_version text NOT NULL,
    policy_hash char(64) NOT NULL,
    evaluation_fingerprint char(64) NOT NULL,
    outcome text NOT NULL CHECK (outcome IN (
        'pass', 'human_review_required', 'block'
    )),
    reason_codes text[] NOT NULL DEFAULT ARRAY[]::text[],
    obligations jsonb NOT NULL DEFAULT '{}'::jsonb,
    evaluated_by text NOT NULL,
    evaluated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX rights_gate_evaluations_run_idx
    ON football_brief.rights_gate_evaluations (workflow_run_id, evaluated_at DESC);
CREATE INDEX rights_gate_evaluations_fingerprint_idx
    ON football_brief.rights_gate_evaluations (evaluation_fingerprint);

CREATE TABLE football_brief.rights_gate_asset_decisions (
    evaluation_id uuid NOT NULL
        REFERENCES football_brief.rights_gate_evaluations(id) ON DELETE RESTRICT,
    asset_id uuid NOT NULL
        REFERENCES football_brief.assets(id) ON DELETE RESTRICT,
    asset_sha256 char(64) NOT NULL,
    selected_asset_rights_id uuid
        REFERENCES football_brief.asset_rights(id) ON DELETE RESTRICT,
    outcome text NOT NULL CHECK (outcome IN (
        'pass', 'human_review_required', 'block'
    )),
    reason_codes text[] NOT NULL DEFAULT ARRAY[]::text[],
    evidence_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    obligations jsonb NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (evaluation_id, asset_id)
);

CREATE INDEX rights_gate_asset_decisions_asset_idx
    ON football_brief.rights_gate_asset_decisions (asset_id, evaluated_at DESC);

CREATE OR REPLACE FUNCTION football_brief.reject_rights_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Rights gate audit records are append-only';
END;
$$;

CREATE TRIGGER rights_gate_evaluations_immutable
BEFORE UPDATE OR DELETE ON football_brief.rights_gate_evaluations
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_rights_audit_mutation();

CREATE TRIGGER rights_gate_asset_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.rights_gate_asset_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.reject_rights_audit_mutation();

COMMENT ON TABLE football_brief.asset_rights_evidence_links IS
    'Links evidence to the exact versioned rights assertion it supports.';
COMMENT ON TABLE football_brief.rights_gate_evaluations IS
    'Append-only aggregate rights decisions at manifest admission, render start, or manual checks.';
COMMENT ON TABLE football_brief.rights_gate_asset_decisions IS
    'Append-only per-asset authorization evidence for each rights gate evaluation.';

COMMIT;
