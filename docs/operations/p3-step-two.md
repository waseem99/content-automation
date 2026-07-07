# P3 Step Two

This step adds the approval gate for P3 options created in step one.

## Flow

1. P3 step one creates requirements and options.
2. `P3StepTwoService.request_review` creates a pending review row for an option.
3. Pending or missing review blocks downstream consumption.
4. `P3StepTwoService.decide` records either `approved` or `returned`.
5. Only approved options can pass `require_approved`.

## Service methods

- `request_review(workflow_run_id, option_id, actor)`
- `decide(workflow_run_id, option_id, status, reviewed_by, rationale)`
- `require_approved(workflow_run_id, option_id)`
- `pending(workflow_run_id)`

## Guardrails

- Wrong-workflow options fail closed.
- Missing review fails closed.
- Pending review fails closed.
- Returned options fail closed.
- This step does not prepare packages, export, render, or publish anything.

## Next step

P3-03 should consume only approved options when creating package-preparation records.
