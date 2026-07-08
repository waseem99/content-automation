# P20 Step 04

This step documents the data retention and deletion evidence pack for production compliance readiness.

Part of #274. Closes #278 after the PR merges.

## Goal

Define audit-ready evidence for retention decisions, deletion routes, replacement routes, redaction handling, owner review, and privacy-safe closure while keeping evidence summary-only and export-safe.

## Source references

This evidence pack builds on:

```text
docs/operations/p20-step-01.md
docs/operations/p20-step-03.md
docs/operations/p19-step-03.md
docs/operations/p19-readiness-report.md
docs/operations/p16-step-05.md
docs/operations/p16-readiness-report.md
docs/operations/p18-step-05.md
```

## Pack status

This data retention and deletion evidence pack is documentation-only.

It does not:

- collect production data;
- delete production records;
- change retention settings;
- export customer data;
- expose restricted values;
- approve production launch;
- schedule production launch;
- publish retention evidence;
- render retention evidence;
- bypass workflow gates.

## Evidence categories

The pack must cover evidence for:

- retention decisions;
- deletion route decisions;
- replacement route decisions;
- redaction decisions;
- rejected evidence decisions;
- evidence owner review;
- reviewer confirmation;
- sensitivity classification;
- privacy escalation;
- compliance closeout linkage.

## Retention decisions

Allowed retention decisions:

- retain summary only;
- retain issue or PR reference only;
- retain CI run identifier only;
- retain merge commit reference only;
- retain evidence archive entry name only;
- redact and retain summary;
- delete or replace evidence;
- reject evidence;
- escalate to evidence owner;
- escalate to security incident response;
- block by guardrail.

Retention decisions must not retain customer data exports, private runtime values, secret values, raw credentials, production tokens, or raw logs with restricted values.

## Deletion and replacement routes

Allowed deletion and replacement routes:

- remove restricted evidence from notes;
- replace with issue or PR reference;
- replace with CI run identifier;
- replace with merge commit reference;
- replace with summarized non-sensitive note;
- replace with evidence archive entry name;
- route to evidence owner;
- route to privacy owner;
- route to security incident response;
- create follow-up issue;
- block by guardrail.

Deletion route documentation must not include the restricted value being removed.

## Required evidence fields

Each retention/deletion evidence item must record:

- evidence item identifier;
- data category;
- source location;
- owner;
- reviewer;
- sensitivity class;
- retention decision;
- deletion route;
- replacement route;
- redaction status;
- evidence source;
- action route;
- action owner;
- review cadence;
- validation requirement;
- closure criteria.

## Sensitivity classes

Allowed sensitivity classes:

- public reference;
- internal summary;
- restricted summary;
- restricted value suspected;
- restricted value confirmed;
- customer data suspected;
- customer data confirmed;
- blocked by guardrail.

Restricted value suspected, restricted value confirmed, customer data suspected, and customer data confirmed require escalation and cannot close without owner review.

## Owner review requirements

Owner review must confirm:

- evidence class is allowed;
- sensitivity class is recorded;
- retention decision is valid;
- deletion route is recorded when required;
- replacement route is recorded when required;
- redaction status is complete when required;
- evidence source is summary-only;
- closure criteria are met;
- no restricted values remain.

## Review cadence

Review cadence options:

- per PR closeout;
- before compliance closeout;
- after privacy escalation;
- after security incident;
- after support pattern;
- after retention rule change;
- monthly during steady operation.

## Stop conditions

Stop retention/deletion evidence closure if:

- evidence item identifier is missing;
- data category is missing;
- source location is missing;
- owner is missing;
- reviewer is missing;
- sensitivity class is missing;
- retention decision is missing;
- deletion route is missing when deletion is required;
- replacement route is missing when replacement is required;
- redaction status is missing when redaction is required;
- evidence source is missing;
- action owner is missing for required action;
- restricted value remains in evidence;
- customer data export is requested;
- private runtime value is present;
- secret value is present;
- raw credential is present;
- production token is present;
- external export is requested;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
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
tests/integration/test_p20_step_04.py
```

The validation checks source references, documentation-only status, evidence categories, retention decisions, deletion and replacement routes, required fields, sensitivity classes, owner review requirements, review cadence, stop conditions, and guardrails.
