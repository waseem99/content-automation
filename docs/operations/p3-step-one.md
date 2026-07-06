# P3 Step One

This step converts step-plan requirements into explicit rows and records options against them.

## Flow

1. A P2 step plan exists.
2. `P3StepOneService.materialize_requirements` creates one row per plan requirement.
3. Operators can add options against each requirement.
4. Duplicate options are reused through a deterministic option hash.
5. Workflow events record materialization and option creation.

## Service methods

- `materialize_requirements(workflow_run_id, step_plan_id, actor)`
- `list_requirements(step_plan_id)`
- `add_option(workflow_run_id, requirement_id, reference_type, reference_value, reference_metadata, notes, actor)`
- `list_options(requirement_id)`

## Guardrails

- Wrong-workflow step plans fail closed.
- Wrong-workflow requirements fail closed.
- Empty option references are rejected.
- This step does not approve options for package preparation.
- This step does not export, render, or publish anything.

## Next step

P3-02 should add the approval gate before package preparation can consume options.

## Validation

Covered by `tests/integration/test_p3_step_one.py` through the P1 Acceptance Harness.
