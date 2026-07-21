-- Detailed, versioned production workflow with immutable review evidence.
-- The existing portfolio_content.stage remains a compatibility projection during migration.

BEGIN;

CREATE TYPE football_brief.production_workflow_stage AS ENUM (
    'concept_draft',
    'concept_review',
    'script_draft',
    'script_review',
    'narration_generation',
    'narration_review',
    'storyboard_generation',
    'storyboard_review',
    'local_preview_generation',
    'local_preview_review',
    'spend_approval',
    'premium_production',
    'final_assembly',
    'final_review',
    'package_preparation',
    'package_approval',
    'scheduling',
    'publication',
    'published'
);

CREATE TYPE football_brief.production_workflow_status AS ENUM (
    'active', 'blocked', 'completed', 'archived'
);

CREATE TYPE football_brief.production_workflow_version_status AS ENUM (
    'working', 'in_review', 'approved', 'changes_requested', 'rejected', 'superseded'
);

CREATE TYPE football_brief.production_workflow_decision AS ENUM (
    'approved', 'changes_requested', 'rejected'
);

CREATE TABLE football_brief.production_workflows (
    id uuid PRIMARY KEY,
    portfolio_content_id uuid NOT NULL UNIQUE REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    current_stage football_brief.production_workflow_stage NOT NULL DEFAULT 'concept_draft',
    status football_brief.production_workflow_status NOT NULL DEFAULT 'active',
    current_version_id uuid NOT NULL,
    lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
    blocked_reason text,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CONSTRAINT blocked_workflow_has_reason CHECK (
        status <> 'blocked' OR nullif(btrim(blocked_reason), '') IS NOT NULL
    ),
    CONSTRAINT completed_workflow_has_timestamp CHECK (
        status <> 'completed' OR completed_at IS NOT NULL
    )
);

CREATE TABLE football_brief.production_workflow_versions (
    id uuid PRIMARY KEY,
    workflow_id uuid NOT NULL REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version >= 1),
    parent_version_id uuid,
    basis_content_version integer NOT NULL CHECK (basis_content_version >= 1),
    status football_brief.production_workflow_version_status NOT NULL DEFAULT 'working',
    revision_reason text,
    snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    last_edited_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    decided_at timestamptz,
    UNIQUE (workflow_id, version),
    UNIQUE (id, workflow_id),
    CONSTRAINT revision_requires_parent CHECK (
        version = 1 OR parent_version_id IS NOT NULL
    ),
    CONSTRAINT first_version_has_no_parent CHECK (
        version <> 1 OR parent_version_id IS NULL
    ),
    CONSTRAINT submitted_version_has_timestamp CHECK (
        status = 'working' OR submitted_at IS NOT NULL
    ),
    CONSTRAINT decided_version_has_timestamp CHECK (
        status NOT IN ('approved', 'changes_requested', 'rejected') OR decided_at IS NOT NULL
    )
);

ALTER TABLE football_brief.production_workflow_versions
    ADD CONSTRAINT production_workflow_version_parent_fk
    FOREIGN KEY (parent_version_id, workflow_id)
    REFERENCES football_brief.production_workflow_versions(id, workflow_id)
    ON DELETE RESTRICT;

ALTER TABLE football_brief.production_workflows
    ADD CONSTRAINT production_workflow_current_version_fk
    FOREIGN KEY (current_version_id, id)
    REFERENCES football_brief.production_workflow_versions(id, workflow_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX production_workflow_one_live_version_idx
ON football_brief.production_workflow_versions (workflow_id)
WHERE status IN ('working', 'in_review');

CREATE INDEX production_workflow_versions_history_idx
ON football_brief.production_workflow_versions (workflow_id, version DESC);

CREATE TRIGGER production_workflow_versions_touch_updated_at
BEFORE UPDATE ON football_brief.production_workflow_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.production_workflow_stage_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid NOT NULL REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL,
    from_stage football_brief.production_workflow_stage,
    to_stage football_brief.production_workflow_stage NOT NULL,
    event text NOT NULL CHECK (event IN (
        'created', 'snapshot_updated', 'submitted', 'approved', 'changes_requested',
        'rejected', 'reopened', 'assignment_changed', 'completed'
    )),
    actor text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text,
    from_lock_version bigint NOT NULL CHECK (from_lock_version >= 0),
    to_lock_version bigint NOT NULL CHECK (to_lock_version = from_lock_version + 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workflow_version_id, workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT
);

CREATE INDEX production_workflow_history_idx
ON football_brief.production_workflow_stage_history (workflow_id, created_at, id);

CREATE TABLE football_brief.production_workflow_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid NOT NULL REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL,
    stage football_brief.production_workflow_stage NOT NULL,
    assignee_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    assigned_by text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    due_at timestamptz,
    active boolean NOT NULL DEFAULT true,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT completed_assignment_is_inactive CHECK (
        completed_at IS NULL OR active = false
    ),
    FOREIGN KEY (workflow_version_id, workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX production_workflow_one_active_assignment_idx
ON football_brief.production_workflow_assignments (workflow_id, workflow_version_id, stage)
WHERE active = true;

CREATE INDEX production_workflow_assignment_inbox_idx
ON football_brief.production_workflow_assignments (assignee_operator_id, active, due_at);

CREATE TABLE football_brief.production_workflow_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_version_id uuid NOT NULL REFERENCES football_brief.production_workflow_versions(id) ON DELETE RESTRICT,
    stage football_brief.production_workflow_stage NOT NULL,
    author_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    comment_type text NOT NULL DEFAULT 'general' CHECK (comment_type IN (
        'general', 'change_request', 'factual', 'tone', 'production'
    )),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    parent_comment_id uuid REFERENCES football_brief.production_workflow_comments(id) ON DELETE RESTRICT,
    resolved_by_operator_id text REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT resolved_comment_is_consistent CHECK (
        (resolved_at IS NULL AND resolved_by_operator_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_operator_id IS NOT NULL)
    )
);

CREATE INDEX production_workflow_comments_idx
ON football_brief.production_workflow_comments (workflow_version_id, stage, created_at);

CREATE TABLE football_brief.production_workflow_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id uuid NOT NULL REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL,
    stage football_brief.production_workflow_stage NOT NULL,
    decision football_brief.production_workflow_decision NOT NULL,
    reviewer_operator_id text NOT NULL REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 3 AND 5000),
    workflow_lock_version bigint NOT NULL CHECK (workflow_lock_version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workflow_version_id, stage),
    FOREIGN KEY (workflow_version_id, workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT
);

CREATE INDEX production_workflow_decisions_idx
ON football_brief.production_workflow_decisions (workflow_id, created_at);

CREATE OR REPLACE FUNCTION football_brief.require_workflow_lock_increment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.lock_version <> OLD.lock_version + 1 THEN
        RAISE EXCEPTION 'Workflow updates must increment lock_version by exactly one';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_workflow_lock_increment
BEFORE UPDATE ON football_brief.production_workflows
FOR EACH ROW EXECUTE FUNCTION football_brief.require_workflow_lock_increment();

CREATE TRIGGER production_workflows_touch_updated_at
BEFORE UPDATE ON football_brief.production_workflows
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE OR REPLACE FUNCTION football_brief.protect_workflow_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Production workflow history and decisions are immutable';
END;
$$;

CREATE TRIGGER production_workflow_history_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_workflow_stage_history
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_workflow_evidence();

CREATE TRIGGER production_workflow_decisions_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_workflow_decisions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_workflow_evidence();

CREATE OR REPLACE FUNCTION football_brief.protect_workflow_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Production workflow versions are immutable evidence';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'working' AND NEW.status = 'in_review' THEN
            NULL;
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('approved', 'changes_requested', 'rejected') THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'Invalid production workflow version status transition';
        END IF;
    END IF;

    IF OLD.status <> 'working' THEN
        IF NEW.workflow_id IS DISTINCT FROM OLD.workflow_id
           OR NEW.version IS DISTINCT FROM OLD.version
           OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
           OR NEW.basis_content_version IS DISTINCT FROM OLD.basis_content_version
           OR NEW.revision_reason IS DISTINCT FROM OLD.revision_reason
           OR NEW.snapshot IS DISTINCT FROM OLD.snapshot
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.last_edited_by IS DISTINCT FROM OLD.last_edited_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
            RAISE EXCEPTION 'Submitted workflow versions are immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_workflow_version_immutable
BEFORE UPDATE OR DELETE ON football_brief.production_workflow_versions
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_workflow_version();

CREATE OR REPLACE FUNCTION football_brief.protect_workflow_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Workflow assignments cannot be deleted';
    END IF;
    IF NEW.workflow_id IS DISTINCT FROM OLD.workflow_id
       OR NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id
       OR NEW.stage IS DISTINCT FROM OLD.stage
       OR NEW.assignee_operator_id IS DISTINCT FROM OLD.assignee_operator_id
       OR NEW.assigned_by IS DISTINCT FROM OLD.assigned_by
       OR NEW.due_at IS DISTINCT FROM OLD.due_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (OLD.active = false AND NEW.active = true)
       OR (OLD.completed_at IS NOT NULL AND NEW.completed_at IS DISTINCT FROM OLD.completed_at) THEN
        RAISE EXCEPTION 'Workflow assignments are append-only except completion';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_workflow_assignment_append_only
BEFORE UPDATE OR DELETE ON football_brief.production_workflow_assignments
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_workflow_assignment();

CREATE OR REPLACE FUNCTION football_brief.protect_workflow_comment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Workflow comments cannot be deleted';
    END IF;
    IF NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id
       OR NEW.stage IS DISTINCT FROM OLD.stage
       OR NEW.author_operator_id IS DISTINCT FROM OLD.author_operator_id
       OR NEW.comment_type IS DISTINCT FROM OLD.comment_type
       OR NEW.body IS DISTINCT FROM OLD.body
       OR NEW.parent_comment_id IS DISTINCT FROM OLD.parent_comment_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (OLD.resolved_at IS NOT NULL AND NEW.resolved_at IS DISTINCT FROM OLD.resolved_at)
       OR (OLD.resolved_by_operator_id IS NOT NULL AND NEW.resolved_by_operator_id IS DISTINCT FROM OLD.resolved_by_operator_id) THEN
        RAISE EXCEPTION 'Workflow comments are append-only except one-time resolution';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER production_workflow_comment_append_only
BEFORE UPDATE OR DELETE ON football_brief.production_workflow_comments
FOR EACH ROW EXECUTE FUNCTION football_brief.protect_workflow_comment();

COMMENT ON TABLE football_brief.production_workflows IS
    'Current detailed production state. lock_version provides optimistic concurrency control.';
COMMENT ON TABLE football_brief.production_workflow_versions IS
    'Versioned working snapshots; requested changes create a new child version instead of rewriting reviewed evidence.';
COMMENT ON TABLE football_brief.production_workflow_stage_history IS
    'Append-only stage, snapshot, assignment, and reopening history.';
COMMENT ON TABLE football_brief.production_workflow_decisions IS
    'Append-only human decisions bound to one exact workflow version and stage.';

COMMIT;