-- Allow Creator Studio to record the explicit acceptance of a user-authored brief.
-- This keeps workflow history semantic instead of misclassifying the transition as a generic snapshot update.

BEGIN;

ALTER TABLE football_brief.production_workflow_stage_history
    DROP CONSTRAINT production_workflow_stage_history_event_check;

ALTER TABLE football_brief.production_workflow_stage_history
    ADD CONSTRAINT production_workflow_stage_history_event_check
    CHECK (event IN (
        'created', 'snapshot_updated', 'submitted', 'approved', 'changes_requested',
        'rejected', 'reopened', 'assignment_changed', 'completed',
        'manual_brief_accepted'
    ));

COMMIT;
