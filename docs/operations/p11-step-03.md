# P11 Step 03

This step documents incident review cadence and action tracking for production operations stabilization.

Part of #157. Closes #160 after the PR merges.

## Goal

Create a consistent process for reviewing production incidents, assigning corrective actions, tracking owners, and closing follow-up work.

## Source references

This runbook builds on:

```text
docs/operations/p11-step-01.md
docs/operations/p11-step-02.md
docs/operations/p10-step-05.md
docs/operations/p10-step-04.md
```

## Incident intake

Record each incident with:

- incident date;
- detected by;
- alert or manual report source;
- affected surface;
- severity;
- customer or operator impact;
- initial owner;
- rollback decision status;
- current state.

## Severity bands

Use these bands:

- S1: service unavailable, data safety concern, or protected route failure;
- S2: degraded health, repeated failures, or rollback decision needed;
- S3: limited operational impact with known workaround;
- S4: observation, noise, or near miss.

Severity may be lowered only after evidence review.

## Review cadence

Review timing:

- S1 within one business day;
- S2 within two business days;
- S3 during the next weekly rollout review;
- S4 during the next alert tuning review.

Recurring review continues until all critical actions are closed.

## Review agenda

Agenda:

1. Confirm incident summary and severity.
2. Review detection path and alert route.
3. Review timeline and response actions.
4. Review rollback or forward-fix decision.
5. Identify root cause or best current explanation.
6. Assign corrective actions.
7. Set owners and due dates.
8. Define closure criteria.
9. Record evidence links.

## Action tracking

Each action item must include:

- action title;
- owner;
- backup owner;
- due date;
- severity link;
- status;
- validation method;
- closure evidence;
- review date.

## Closure criteria

Close an incident only when:

- required evidence is recorded;
- critical actions are complete or formally accepted;
- owner confirms no unresolved rollback concern;
- alert follow-up is complete or tracked;
- evidence archive owner confirms archive entry;
- decision owner approves closure.

## Stop conditions

Do not close or downgrade if:

- protected route failure is unresolved;
- health or readiness failure remains active;
- rollback owner is unavailable;
- critical action has no owner;
- evidence includes secret values;
- workflow gate bypass is requested;
- decision owner has not approved closure.

## Guardrails

- No incident closure without evidence.
- No downgrade without evidence review.
- No automatic approval.
- No workflow gate bypass.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p11_step_03.py
```

The validation checks source references, intake, severity, cadence, agenda, action tracking, closure criteria, stop conditions, and guardrails.
