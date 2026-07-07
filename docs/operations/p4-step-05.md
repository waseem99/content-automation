# P4 Step 05

This step adds a read-only audit report for workflow runs.

## Service

`P4AuditReportService.report(workflow_run_id=...)`

The report returns one JSON-friendly payload for an operator or future API/dashboard layer.

## Report sections

- `workflow` — workflow metadata, content item, status, cost, current stage, and failure reason.
- `status` — computed summary including blocked reason, queue count, event count, review count, package count, and manifest count.
- `timeline` — workflow events ordered by creation time and id.
- `stages` — stage execution rows.
- `reviews` — packet, source output, option, plan, and package review states.
- `queue` — current operator queue cards from dashboard contracts.
- `packages` — P3 package rows with final review status.
- `manifests` — P3 delivery manifest rows.

## Blocked and failure context

The report computes `status.is_blocked` and `status.blocked_reason` from:

1. workflow failure reason, when present;
2. failed workflow status;
3. current operator queue cards;
4. non-approved review states.

## Guardrails

- Read-only; no state mutation.
- No new audit table or migration.
- No publishing, scheduling, rendering, or external export.
- Existing workflow events and review tables remain authoritative.
- Missing workflow ids return `ok: false`.

## Validation

Covered by `tests/integration/test_p4_step_05.py` through the P1 Acceptance Harness P4 wildcard entry.
