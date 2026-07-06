# Workflow State Machine

Issue #8 introduces a controlled workflow state machine. Status changes should go through `WorkflowStateMachine`; direct database status updates are blocked by PostgreSQL triggers.

## Workflow statuses

- active
- blocked
- failed
- cancelled
- archived
- completed

## Stage statuses

- pending
- running
- completed
- failed
- needs_revision
- awaiting_human
- rejected
- skipped
- superseded

## Guarantees

- Invalid transitions raise stable reason codes.
- Accepted transitions append workflow events.
- Manual/operator transitions require actor and reason.
- Retry creates a new stage execution attempt.
- Old attempts and evidence remain unchanged.
- Dependencies are stored in `stage_dependencies`.
- When an upstream output hash changes, downstream stages with stale expected hashes become `superseded`.
- Resume plans skip completed stages and return only invalid, failed, pending, rejected, needs-revision, or superseded stages as runnable.
- Workflows cannot complete while required stages remain pending, running, failed, awaiting human review, rejected, or needing revision.

## Operational rule

Application code should not update `workflow_runs.status` or `stage_executions.status` directly. Use `WorkflowStateMachine.transition_workflow`, `transition_stage`, `retry_stage`, `add_dependency`, and `resume_plan`.
