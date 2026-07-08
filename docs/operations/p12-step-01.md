# P12 Step 01

This step documents release calendar governance for production lifecycle governance.

Part of #170. Closes #171 after the PR merges.

## Goal

Create a governed release calendar so production changes have planned windows, clear owners, required readiness evidence, and documented stop conditions.

## Source references

This runbook builds on:

```text
docs/operations/p11-readiness-report.md
docs/operations/p11-closeout-checklist.md
docs/operations/p11-step-05.md
```

## Calendar ownership

Required roles:

- release calendar owner;
- decision owner;
- operations owner;
- deployment owner;
- rollback owner;
- monitoring owner;
- incident review owner;
- evidence archive owner;
- security or guardrail reviewer.

Each role must have a primary owner and backup owner before a release window is accepted.

## Release windows

Each release window must record:

- release date;
- release type;
- change summary;
- affected surface;
- expected user or operator impact;
- readiness evidence link;
- rollback readiness link;
- monitoring plan;
- decision owner approval;
- evidence archive entry.

## Blackout windows

Blackout windows must be recorded for:

- known high-risk business periods;
- active incidents;
- unresolved rollback gaps;
- missing monitoring coverage;
- missing owner coverage;
- open critical governance exceptions.

Release expansion is not allowed during a blackout window.

## Readiness inputs

Required readiness inputs:

- release calendar entry;
- owner and backup owner list;
- deployment checklist status;
- monitoring coverage status;
- rollback readiness status;
- open incident status;
- open exception status;
- evidence archive status.

## Change record

Every governed release must have a change record with:

- change ID;
- release window;
- linked issue or PR;
- decision owner;
- implementation owner;
- approval status;
- validation status;
- rollback decision status;
- final outcome.

## Approval path

A release window may proceed only when:

- decision owner approves the release window;
- deployment owner confirms readiness;
- rollback owner confirms rollback path;
- monitoring owner confirms coverage;
- evidence archive owner confirms record location;
- guardrail reviewer confirms no blocked condition.

## Stop conditions

Stop release activity if:

- blackout window is active;
- decision owner approval is missing;
- rollback readiness is missing;
- monitoring coverage is missing;
- required owner or backup is missing;
- active incident blocks the release;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No release without calendar entry.
- No release during blackout window.
- No release without decision owner approval.
- No release without rollback readiness.
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
tests/integration/test_p12_step_01.py
```

The validation checks source references, calendar ownership, release windows, blackout windows, readiness inputs, change records, approval path, stop conditions, guardrails, and P12 CI wildcard coverage.
