# P12 Step 05

This step documents governance exception handling for production lifecycle governance.

Part of #170. Closes #175 after the PR merges.

## Goal

Create a controlled path for time-limited governance exceptions that require explicit ownership, decision approval, compensating controls, evidence, and expiry.

## Source references

This runbook builds on:

```text
docs/operations/p12-step-01.md
docs/operations/p12-step-02.md
docs/operations/p12-step-03.md
docs/operations/p12-step-04.md
```

## Exception request fields

Each exception request must include:

- exception ID;
- requester;
- exception owner;
- affected control or process;
- reason;
- business need;
- risk statement;
- compensating control;
- requested start date;
- requested expiry date;
- evidence archive entry.

## Approval path

Required approvals:

- exception owner accepts ownership;
- affected control owner confirms impact;
- security or guardrail reviewer confirms risk notes;
- decision owner approves or rejects;
- evidence archive owner confirms archive location.

## Time limits

Exception time limits:

- every exception must have an expiry date;
- default review period is monthly;
- critical exceptions require weekly review;
- expired exceptions must be closed or re-approved;
- permanent exceptions are not allowed.

## Compensating controls

Compensating controls must include:

- control owner;
- mitigation description;
- validation method;
- monitoring owner;
- evidence source;
- review cadence;
- failure action.

## Review cadence

Review exceptions:

- weekly for critical exceptions;
- monthly for normal exceptions;
- during KPI reporting;
- during audit control review;
- before release window approval when relevant;
- before P12 closeout.

## Closure criteria

Close an exception only when:

- expiry date is reached or need is removed;
- compensating control is no longer needed or is replaced;
- evidence is archived;
- control owner signs off;
- decision owner accepts closure;
- KPI report is updated if applicable.

## Stop conditions

Stop exception approval or renewal if:

- exception owner is missing;
- affected control is unknown;
- expiry date is missing;
- compensating control is missing;
- decision owner approval is missing;
- exception hides a critical production failure;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No permanent exceptions.
- No exception without expiry date.
- No exception without compensating control.
- No exception without decision owner approval.
- No exception that hides critical production failure.
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
tests/integration/test_p12_step_05.py
```

The validation checks source references, request fields, approval path, time limits, compensating controls, review cadence, closure criteria, stop conditions, and guardrails.
