# P5 Step 04

This step adds explicit API contract coverage for P5 routes.

## Test file

```text
tests/integration/test_p5_step_04.py
```

## Coverage

- health route shape
- runtime config route shape
- workflow queue shape
- dashboard queue-card shape
- dashboard schema shape
- demo scenario/start/status/current-approval flow
- audit report shape
- wrong-workflow approval failure
- invalid id handling
- missing request body handling
- unsupported approval action handling
- missing and invalid operator key handling

## Contract expectations

The tests check stable fields rather than only status codes. This protects the future operator UI/API consumers from accidental response-shape drift.

## Guardrails

- No route business logic is duplicated.
- No publishing, scheduling, rendering, or external export is added.
- Approval actions remain explicit.
- Wrong workflow/resource combinations fail closed.
- Protected routes require a valid operator key.

## Validation

The test file is covered by the existing P1 Acceptance Harness wildcard:

```text
tests/integration/test_p5_step_*.py
```
