# P22 Step 04

This step documents the data access and role review for production privacy and data-governance readiness.

Part of #300. Closes #304 after the PR merges.

## Goal

Define who may access each data class, which role boundaries apply, how approvals work, how access is reviewed, when access should be removed, and what stops closure.

## Source references

This review builds on:

```text
docs/operations/p22-step-01.md
docs/operations/p22-step-03.md
docs/operations/p20-step-02.md
docs/operations/p20-step-03.md
docs/operations/p19-step-02.md
docs/operations/p18-step-02.md
docs/operations/p18-step-05.md
```

## Review status

This data access and role review is documentation-only.

It does not:

- grant production access;
- remove production access;
- change repository permissions;
- expose restricted data;
- approve production launch;
- schedule access reviews;
- publish access evidence;
- render access evidence;
- bypass workflow gates;
- replace owner approval.

## Data access boundaries

Access boundaries must cover:

- public reference data;
- internal summary data;
- restricted summary data;
- suspected restricted data;
- confirmed restricted data;
- suspected customer data;
- confirmed customer data;
- blocked by guardrail data.

## Role mapping

Required role mapping:

- data owner;
- evidence owner;
- operator owner;
- support owner;
- incident owner;
- release owner;
- documentation owner;
- reviewer;
- backup owner.

## Approval rules

Approval rules:

- no access change without named owner;
- no sensitive access without reviewer confirmation;
- no shared accounts;
- no permanent elevated access;
- no access exception without expiry or review point;
- no access approval for customer data export;
- no access approval for secret values in evidence;
- no automatic access changes.

## Review cadence

Review cadence options:

- per role change;
- before privacy closeout;
- after incident signal;
- after support escalation;
- after drill finding;
- after owner change;
- monthly during steady operation.

## Removal triggers

Access must be removed or re-reviewed when:

- owner changes;
- reviewer is missing;
- role no longer requires access;
- access exceeds data class boundary;
- exception expires;
- evidence sensitivity changes;
- incident signal appears;
- customer data is suspected;
- restricted value is confirmed;
- workflow gate bypass is requested.

## Required review fields

Each access review item must record:

- access review identifier;
- role name;
- data class;
- access boundary;
- current access summary;
- requested access summary;
- owner;
- reviewer;
- approval route;
- evidence source;
- evidence sensitivity;
- review cadence;
- removal trigger status;
- exception status;
- validation requirement;
- closure criteria.

## Allowed approval routes

Allowed approval routes:

- no access change required;
- approve summary-only access;
- approve time-limited exception;
- reject with reason;
- remove stale access;
- request more evidence;
- escalate to data owner;
- escalate to evidence owner;
- escalate to incident owner;
- block by guardrail.

## Stop conditions

Stop access review closure if:

- access review identifier is missing;
- role name is missing;
- data class is missing;
- access boundary is missing;
- owner is missing;
- reviewer is missing;
- approval route is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- review cadence is missing;
- exception is permanent;
- sensitive access lacks reviewer confirmation;
- access approval implies customer data export;
- secret value is present;
- private runtime value is present;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic access changes.
- No workflow gate bypass.
- No public production launch without explicit decision.
- No release without calendar entry.
- No release during blackout window.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No permanent exceptions.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p22_step_04.py
```

The validation checks source references, documentation-only status, data access boundaries, role mapping, approval rules, cadence, removal triggers, required fields, approval routes, stop conditions, and guardrails.
