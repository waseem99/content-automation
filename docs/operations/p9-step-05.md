# P9 Step 05

This step documents the final go/no-go checklist for controlled production rollout readiness.

Part of #131. Closes #136 after the PR merges.

## Goal

Provide a clear, evidence-based decision checklist before any controlled production rollout proceeds.

## Source references

This checklist builds on:

```text
docs/operations/p9-step-01.md
docs/operations/p9-step-02.md
docs/operations/p9-step-03.md
docs/operations/p9-step-04.md
```

## Decision options

The final decision must be one of:

- go;
- no-go;
- go with documented limitations;
- defer pending evidence;
- repeat rehearsal.

## Required evidence

Required evidence before go decision:

- deployment dry-run result;
- restore rehearsal result;
- rollback rehearsal result;
- dashboard review result;
- alert routing review result;
- latest exact-head CI result;
- backup availability confirmation;
- rollback owner confirmation;
- decision owner confirmation;
- unresolved gap list.

## Approval gates

Required approval gates:

- deployment operator sign-off;
- database operator sign-off;
- dashboard or alert reviewer sign-off;
- security or guardrail reviewer sign-off;
- decision owner sign-off.

Approval must be human-recorded and must not be automatic.

## Go criteria

A go decision requires:

- deployment dry-run passed;
- restore rehearsal passed;
- rollback rehearsal passed;
- dashboards reviewed;
- alert routing reviewed;
- latest CI green;
- backup available;
- rollback owner available;
- protected routes verified;
- no secret exposure found;
- no workflow gate bypass needed;
- stop conditions clear.

## No-go criteria

A no-go decision is required if:

- deployment dry-run failed;
- restore rehearsal failed;
- rollback rehearsal failed;
- health or readiness checks failed;
- migration readiness failed;
- protected route access is not enforced;
- alert owner is unknown;
- rollback owner is unavailable;
- backup availability is unknown;
- dashboards expose secrets;
- workflow gate bypass is required;
- latest CI is not green.

## Go with limitations

Go with documented limitations is allowed only when:

- limitation is non-critical;
- limitation does not affect health, readiness, backup, restore, rollback, protected routes, or workflow gates;
- owner and due date are recorded;
- decision owner accepts the limitation.

## Evidence record

Record:

- decision date;
- decision option;
- decision owner;
- deployment operator;
- database operator;
- dashboard reviewer;
- alert routing reviewer;
- CI run IDs;
- rehearsal evidence links or references;
- open limitations;
- stop condition review result;
- next action.

Do not record secret values, tokens, connection strings, raw operator keys, or private runtime values.

## Stop condition review

Before a go decision, confirm none of these are true:

- public production launch is being attempted without approval;
- healthcheck failure exists;
- readiness failure exists;
- migration readiness failure exists;
- backup is missing;
- rollback path is unknown;
- alert route is unknown;
- protected routes are not protected;
- workflow gate bypass is required;
- evidence includes secret values.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No public production launch without explicit go decision.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p9_step_05.py
```

The validation checks source references, decision options, required evidence, approval gates, go criteria, no-go criteria, limitations, evidence record, stop condition review, and guardrails.
