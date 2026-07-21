-- Cross-media Creator Studio comments, structured revision tasks, and unified review inbox.
-- Canonical script, audio, visual, and workflow versions remain the source of truth.

BEGIN;

CREATE TABLE football_brief.creator_review_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    production_workflow_id uuid NOT NULL
        REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL,
    stage football_brief.production_workflow_stage NOT NULL,
    target_type text NOT NULL CHECK (target_type IN (
        'workflow_version', 'script_version', 'script_section',
        'audio_mix_version', 'audio_paragraph',
        'visual_shot_version', 'visual_candidate'
    )),
    target_workflow_version_id uuid,
    target_script_version_id uuid,
    target_script_section_id uuid,
    target_audio_mix_version_id uuid,
    target_audio_paragraph_id uuid,
    target_visual_shot_version_id uuid,
    target_visual_candidate_id uuid,
    timeline_start_ms bigint CHECK (timeline_start_ms IS NULL OR timeline_start_ms >= 0),
    timeline_end_ms bigint CHECK (timeline_end_ms IS NULL OR timeline_end_ms > timeline_start_ms),
    comment_type text NOT NULL DEFAULT 'general' CHECK (comment_type IN (
        'general', 'change_request', 'factual', 'tone', 'timing',
        'continuity', 'accessibility', 'rights'
    )),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    blocking boolean NOT NULL DEFAULT false,
    author_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_by_operator_id text
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT creator_review_comment_one_target CHECK (
        num_nonnulls(
            target_workflow_version_id,
            target_script_version_id,
            target_script_section_id,
            target_audio_mix_version_id,
            target_audio_paragraph_id,
            target_visual_shot_version_id,
            target_visual_candidate_id
        ) = 1
    ),
    CONSTRAINT creator_review_comment_target_matches_type CHECK (
        (target_type='workflow_version' AND target_workflow_version_id IS NOT NULL)
        OR (target_type='script_version' AND target_script_version_id IS NOT NULL)
        OR (target_type='script_section' AND target_script_section_id IS NOT NULL)
        OR (target_type='audio_mix_version' AND target_audio_mix_version_id IS NOT NULL)
        OR (target_type='audio_paragraph' AND target_audio_paragraph_id IS NOT NULL)
        OR (target_type='visual_shot_version' AND target_visual_shot_version_id IS NOT NULL)
        OR (target_type='visual_candidate' AND target_visual_candidate_id IS NOT NULL)
    ),
    CONSTRAINT creator_review_comment_resolution_consistent CHECK (
        (resolved_at IS NULL AND resolved_by_operator_id IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_operator_id IS NOT NULL)
    ),
    CONSTRAINT creator_review_timeline_pair CHECK (
        (timeline_start_ms IS NULL AND timeline_end_ms IS NULL)
        OR (timeline_start_ms IS NOT NULL AND timeline_end_ms IS NOT NULL)
    ),
    CONSTRAINT creator_review_timeline_audio_only CHECK (
        timeline_start_ms IS NULL OR target_type='audio_mix_version'
    ),
    FOREIGN KEY (workflow_version_id, production_workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (target_workflow_version_id, production_workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (target_script_version_id)
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_script_section_id)
        REFERENCES football_brief.script_sections(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_audio_mix_version_id)
        REFERENCES football_brief.audio_mix_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_audio_paragraph_id)
        REFERENCES football_brief.audio_paragraphs(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_visual_shot_version_id)
        REFERENCES football_brief.visual_shot_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_visual_candidate_id)
        REFERENCES football_brief.visual_candidates(id) ON DELETE RESTRICT
);

CREATE INDEX creator_review_comments_content_idx
ON football_brief.creator_review_comments
    (portfolio_content_id, stage, resolved_at, created_at DESC);

CREATE INDEX creator_review_comments_target_idx
ON football_brief.creator_review_comments
    (target_type, resolved_at, blocking, created_at DESC);

CREATE TABLE football_brief.creator_revision_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_comment_id uuid NOT NULL UNIQUE
        REFERENCES football_brief.creator_review_comments(id) ON DELETE RESTRICT,
    portfolio_content_id uuid NOT NULL
        REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    production_workflow_id uuid NOT NULL
        REFERENCES football_brief.production_workflows(id) ON DELETE RESTRICT,
    workflow_version_id uuid NOT NULL,
    stage football_brief.production_workflow_stage NOT NULL,
    target_type text NOT NULL CHECK (target_type IN (
        'workflow_version', 'script_version', 'script_section',
        'audio_mix_version', 'audio_paragraph',
        'visual_shot_version', 'visual_candidate'
    )),
    target_workflow_version_id uuid,
    target_script_version_id uuid,
    target_script_section_id uuid,
    target_audio_mix_version_id uuid,
    target_audio_paragraph_id uuid,
    target_visual_shot_version_id uuid,
    target_visual_candidate_id uuid,
    task_type text NOT NULL CHECK (task_type IN (
        'workflow_update', 'script_edit', 'factual_support', 'tone_edit',
        'audio_retake', 'audio_mix', 'visual_prompt', 'visual_candidate',
        'accessibility', 'rights', 'general'
    )),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 300),
    instructions text NOT NULL CHECK (length(btrim(instructions)) BETWEEN 3 AND 5000),
    assignee_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    assigned_by_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    due_at timestamptz,
    priority text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','completed','cancelled')),
    blocker boolean NOT NULL DEFAULT true,
    lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version >= 1),
    started_at timestamptz,
    completed_at timestamptz,
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT creator_revision_task_one_target CHECK (
        num_nonnulls(
            target_workflow_version_id,
            target_script_version_id,
            target_script_section_id,
            target_audio_mix_version_id,
            target_audio_paragraph_id,
            target_visual_shot_version_id,
            target_visual_candidate_id
        ) = 1
    ),
    CONSTRAINT creator_revision_task_target_matches_type CHECK (
        (target_type='workflow_version' AND target_workflow_version_id IS NOT NULL)
        OR (target_type='script_version' AND target_script_version_id IS NOT NULL)
        OR (target_type='script_section' AND target_script_section_id IS NOT NULL)
        OR (target_type='audio_mix_version' AND target_audio_mix_version_id IS NOT NULL)
        OR (target_type='audio_paragraph' AND target_audio_paragraph_id IS NOT NULL)
        OR (target_type='visual_shot_version' AND target_visual_shot_version_id IS NOT NULL)
        OR (target_type='visual_candidate' AND target_visual_candidate_id IS NOT NULL)
    ),
    CONSTRAINT creator_revision_task_status_times CHECK (
        (status <> 'in_progress' OR started_at IS NOT NULL)
        AND (status <> 'completed' OR completed_at IS NOT NULL)
        AND (status <> 'cancelled' OR cancelled_at IS NOT NULL)
    ),
    FOREIGN KEY (workflow_version_id, production_workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (target_workflow_version_id, production_workflow_id)
        REFERENCES football_brief.production_workflow_versions(id, workflow_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (target_script_version_id)
        REFERENCES football_brief.script_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_script_section_id)
        REFERENCES football_brief.script_sections(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_audio_mix_version_id)
        REFERENCES football_brief.audio_mix_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_audio_paragraph_id)
        REFERENCES football_brief.audio_paragraphs(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_visual_shot_version_id)
        REFERENCES football_brief.visual_shot_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_visual_candidate_id)
        REFERENCES football_brief.visual_candidates(id) ON DELETE RESTRICT
);

CREATE INDEX creator_revision_tasks_inbox_idx
ON football_brief.creator_revision_tasks
    (assignee_operator_id, status, blocker, due_at, priority);

CREATE INDEX creator_revision_tasks_content_idx
ON football_brief.creator_revision_tasks
    (portfolio_content_id, stage, status, created_at DESC);

CREATE TRIGGER creator_revision_tasks_touch_updated_at
BEFORE UPDATE ON football_brief.creator_revision_tasks
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.creator_revision_task_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL
        REFERENCES football_brief.creator_revision_tasks(id) ON DELETE RESTRICT,
    event text NOT NULL CHECK (event IN (
        'created', 'started', 'completed', 'cancelled',
        'reassigned', 'due_changed', 'priority_changed', 'blocker_changed'
    )),
    actor_operator_id text NOT NULL
        REFERENCES football_brief.operator_users(operator_id) ON DELETE RESTRICT,
    from_lock_version bigint CHECK (from_lock_version IS NULL OR from_lock_version >= 1),
    to_lock_version bigint NOT NULL CHECK (to_lock_version >= 1),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(details)='object'),
    CHECK (
        (event='created' AND from_lock_version IS NULL AND to_lock_version=1)
        OR (event<>'created' AND from_lock_version IS NOT NULL AND to_lock_version=from_lock_version+1)
    )
);

CREATE INDEX creator_revision_task_events_idx
ON football_brief.creator_revision_task_events (task_id, created_at, id);

CREATE OR REPLACE VIEW football_brief.creator_review_inbox AS
SELECT
    'workflow_assignment'::text AS inbox_item_type,
    pwa.id AS inbox_item_id,
    mp.brand_id,
    b.slug AS brand_slug,
    b.display_name AS brand_name,
    pc.id AS portfolio_content_id,
    pc.title AS content_title,
    pw.id AS production_workflow_id,
    pwa.workflow_version_id AS exact_version_id,
    pwa.stage::text AS stage,
    pwa.assignee_operator_id,
    pwa.due_at,
    CASE WHEN pwa.active THEN 'open' ELSE 'completed' END::text AS status,
    (pw.status='blocked') AS blocker,
    pw.blocked_reason AS blocker_reason,
    (pwa.active AND pwa.due_at IS NOT NULL AND pwa.due_at < now()) AS overdue,
    'workflow_version'::text AS target_type,
    pwa.workflow_version_id AS target_id,
    pwa.created_at
FROM football_brief.production_workflow_assignments pwa
JOIN football_brief.production_workflows pw ON pw.id=pwa.workflow_id
JOIN football_brief.portfolio_content pc ON pc.id=pw.portfolio_content_id
JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
JOIN football_brief.brands b ON b.id=mp.brand_id
UNION ALL
SELECT
    'revision_task'::text AS inbox_item_type,
    crt.id AS inbox_item_id,
    mp.brand_id,
    b.slug AS brand_slug,
    b.display_name AS brand_name,
    pc.id AS portfolio_content_id,
    pc.title AS content_title,
    crt.production_workflow_id,
    crt.workflow_version_id AS exact_version_id,
    crt.stage::text AS stage,
    crt.assignee_operator_id,
    crt.due_at,
    crt.status,
    crt.blocker,
    CASE WHEN crt.blocker THEN crt.instructions ELSE NULL END AS blocker_reason,
    (crt.status IN ('open','in_progress') AND crt.due_at IS NOT NULL AND crt.due_at < now()) AS overdue,
    crt.target_type,
    COALESCE(
        crt.target_workflow_version_id,
        crt.target_script_version_id,
        crt.target_script_section_id,
        crt.target_audio_mix_version_id,
        crt.target_audio_paragraph_id,
        crt.target_visual_shot_version_id,
        crt.target_visual_candidate_id
    ) AS target_id,
    crt.created_at
FROM football_brief.creator_revision_tasks crt
JOIN football_brief.portfolio_content pc ON pc.id=crt.portfolio_content_id
JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
JOIN football_brief.brands b ON b.id=mp.brand_id;

COMMENT ON TABLE football_brief.creator_review_comments IS
    'Exact-version cross-media comments and optional timed audio annotations for the Creator Studio workspace.';
COMMENT ON TABLE football_brief.creator_revision_tasks IS
    'Structured, assigned revision work created from immutable change-request comments.';
COMMENT ON VIEW football_brief.creator_review_inbox IS
    'Unified filterable inbox over canonical workflow assignments and structured revision tasks.';

COMMIT;
