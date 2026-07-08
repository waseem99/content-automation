# P19 Step 02

This step documents access control and permission review controls for production security readiness.

Part of #261. Closes #263 after the PR merges.

## Goal

Define least-privilege access expectations, permission boundaries, approval routes, review cadence, evidence handling, escalation rules, and stop conditions for production roles.

## Source references

This access review builds on:

```text
docs/operations/p19-step-01.md
docs/operations/p18-step-02.md
docs/operations/p18-step-05.md
docs/operations/p17-step-04.md
docs/operations/p17-step-02.md
docs/operations/p16-readiness-report.md
docs/operations/p14-step-06.md
```

## Review status

This access review is documentation-only.

It does not:

- grant production access;
- remove production access;
- modify repository permissions;
- approve production launch;
- schedule production launch;
- execute release activities;
- bypass workflow gates;
- publish access material;
- export access evidence;
- replace manual approval.

## Least-privilege principles

Access control must follow these principles:

- grant only the access needed for the assigned role;
- separate operator, reviewer, support, release, incident, evidence, and admin responsibilities;
- require owner approval for permission changes;
- require reviewer confirmation for sensitive access;
- require periodic access review;
- remove stale or ownerless access through a tracked route;
- avoid shared accounts;
- avoid undocumented exceptions;
- avoid permanent elevated access;
- record evidence-safe access summaries only.

## Role-to-access boundaries

Role boundaries must define:

- admin access boundary;
- reviewer access boundary;
- operator access boundary;
- support owner access boundary;
- release owner access boundary;
- incident owner access boundary;
- evidence owner access boundary;
- documentation owner access boundary;
- backup owner access boundary.

Each boundary must list allowed actions, prohibited actions, escalation triggers, and evidence expectations.

## Permission review fields

Each permission review item must record:

- access item identifier;
- role name;
- access area;
- current access summary;
- requested access summary;
- owner;
- reviewer;
- approval route;
- evidence source;
- evidence sensitivity;
- least-privilege status;
- exception status;
- review cadence;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Approval routes

Allowed approval routes:

- no access change required;
- approve with named owner;
- approve with time limit;
- reject with reason;
- remove stale access;
- request more evidence;
- escalate to admin owner;
- escalate to evidence owner;
- escalate to security incident response;
- create implementation issue;
- block by guardrail.

Access changes cannot be automatic.

## Review cadence

Access review cadence must include:

- per role change;
- before release decision;
- after incident;
- after support escalation;
- after owner change;
- monthly during steady operation;
- before phase closeout.

## Permission exceptions

Permission exceptions must record:

- exception identifier;
- exception owner;
- business reason summary;
- approval owner;
- reviewer;
- expiry or review point;
- compensating control;
- evidence source;
- action route.

Permission exceptions cannot be permanent.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized access notes;
- summarized approval notes;
- summarized reviewer notes;
- summarized exception notes;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- raw permission dumps with restricted values;
- rendered access materials;
- scheduled access outputs.

## Escalation rules

Escalate when:

- access owner is missing;
- reviewer is missing;
- requested access exceeds role boundary;
- elevated access has no expiry;
- stale access is detected;
- shared account is detected;
- permission exception lacks approval;
- access evidence contains restricted values;
- workflow gate bypass is requested;
- access request implies production launch.

## Stop conditions

Stop access review closure if:

- role name is missing;
- access area is missing;
- owner is missing;
- reviewer is missing;
- approval route is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- least-privilege status is missing;
- review cadence is missing;
- exception has no expiry or review point;
- exception is permanent;
- access change is automatic;
- production launch is implied;
- workflow gate bypass is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- customer data export is requested;
- external export is requested.

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
tests/integration/test_p19_step_02.py
```

The validation checks source references, documentation-only status, least-privilege principles, role boundaries, permission review fields, approval routes, review cadence, permission exceptions, evidence rules, escalation rules, stop conditions, and guardrails.
