# P10 Step 01

This step documents the production exposure decision record for controlled rollout implementation.

Part of #144. Closes #145 after the PR merges.

## Goal

Create a human-owned decision record before any production exposure is enabled.

## Source references

This decision record builds on:

```text
docs/operations/p9-readiness-report.md
docs/operations/p9-step-05.md
docs/operations/p9-closeout-checklist.md
```

## Decision states

Allowed decision states:

- go;
- no-go;
- go with documented limitations;
- defer pending evidence;
- repeat rehearsal.

No decision may be inferred automatically from CI alone.

## Required decision fields

Record these fields:

- decision date;
- decision state;
- decision owner;
- deployment operator;
- database operator;
- dashboard reviewer;
- alert routing reviewer;
- security or guardrail reviewer;
- exact commit SHA;
- exact PR number;
- CI run IDs;
- rehearsal evidence references;
- known limitations;
- stop condition review result;
- next action.

## Required evidence

Before a go decision, confirm:

- P9 readiness report exists;
- P9 go/no-go checklist exists;
- deployment dry-run evidence exists;
- restore rehearsal evidence exists;
- rollback rehearsal evidence exists;
- dashboard review evidence exists;
- alert routing evidence exists;
- latest exact-head CI is green;
- rollback owner is available;
- backup availability is confirmed;
- protected routes are verified.

## Human approvals

Required approvals:

- decision owner approval;
- deployment operator approval;
- database operator approval;
- dashboard or alert reviewer approval;
- security or guardrail reviewer approval.

Approvals must be human-recorded and must not be automatic.

## Limitation handling

A go with documented limitations decision is allowed only when:

- limitation is non-critical;
- limitation does not affect health, readiness, backup, restore, rollback, protected routes, workflow gates, or secret handling;
- limitation owner is recorded;
- limitation due date is recorded;
- decision owner accepts the limitation.

## Stop conditions

A no-go or defer decision is required if any of these are true:

- latest exact-head CI is not green;
- decision owner is unavailable;
- rollback owner is unavailable;
- backup availability is unknown;
- health or readiness checks fail;
- protected route access is not enforced;
- workflow gate bypass is required;
- evidence includes secret values;
- private runtime values are exposed;
- production exposure has no explicit go decision.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No production exposure without explicit go decision.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p10_step_01.py
```

The validation checks source references, decision states, required fields, evidence, approvals, limitations, stop conditions, guardrails, and P10 CI wildcard coverage.
