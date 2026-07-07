# P3 Step Three

This step prepares deterministic package records from an approved step plan and approved P3 options.

## Flow

1. P3 step one creates requirements and options.
2. P3 step two approves the options that may be used downstream.
3. P3 step three records step-plan review status.
4. Package preparation is blocked until the step plan is approved.
5. Package preparation is blocked until every selected option is approved.
6. The worker creates a deterministic package output.
7. The service stores a package row with option IDs, scene map, lineage refs, package hash, metadata, and stage execution ID.

## Service methods

Plan review:

- `P3PlanReviewService.request_review(workflow_run_id, step_plan_id, actor)`
- `P3PlanReviewService.decide(workflow_run_id, step_plan_id, status, reviewed_by, rationale)`
- `P3PlanReviewService.require_approved(workflow_run_id, step_plan_id)`

Package preparation:

- `P3PackageService.create_for_plan(workflow_run_id, step_plan_id, option_ids, actor)`

## Guardrails

- Missing step-plan approval blocks package preparation.
- Pending or returned step-plan approval blocks package preparation.
- Missing option approval blocks package preparation.
- Pending or returned options block package preparation.
- Options must belong to the selected step plan.
- Duplicate package requests reuse the existing worker output and package row.
- This step does not export, publish, or render anything.

## Next step

P3-04 should add the final package approval gate before export manifest generation.
