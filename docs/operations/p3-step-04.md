# P3 Step 04

This step adds the final package approval gate before the next delivery step.

## Flow

1. P3 step three creates a deterministic package row.
2. `P3PackageReviewService.request_review` creates a pending package review.
3. Missing or pending package review blocks downstream use.
4. `P3PackageReviewService.decide` records either `approved` or `returned`.
5. Only approved packages can pass `require_approved`.

## Service methods

- `request_review(workflow_run_id, package_id, actor)`
- `decide(workflow_run_id, package_id, status, reviewed_by, rationale, decision_metadata)`
- `require_approved(workflow_run_id, package_id)`
- `pending(workflow_run_id)`

## Operator queue

`OperatorReviewTools.queue` surfaces `package_review` items for packages with missing, pending, or returned review status.

## Guardrails

- Wrong-workflow packages fail closed.
- Missing package approval fails closed.
- Pending package approval fails closed.
- Returned package approval fails closed.
- Invalid decision status is rejected.
- This step does not generate delivery outputs, export, publish, or render anything.

## Next step

P3-05 should consume only final-approved packages when generating delivery manifests.
