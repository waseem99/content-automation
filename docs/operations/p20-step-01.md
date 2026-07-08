# P20 Step 01

This step documents the privacy compliance evidence index for production audit readiness.

Part of #274. Closes #275 after the PR merges.

## Goal

Create an audit-ready index for privacy-related evidence without copying customer data, private runtime values, secret values, or restricted operational details into compliance records.

## Source references

This index builds on:

```text
docs/operations/p19-step-03.md
docs/operations/p19-readiness-report.md
docs/operations/p18-step-01.md
docs/operations/p18-step-04.md
docs/operations/p18-step-05.md
docs/operations/p17-step-05.md
docs/operations/p16-step-05.md
docs/operations/p16-readiness-report.md
```

## Index status

This privacy compliance evidence index is documentation-only.

It does not:

- collect production data;
- export customer data;
- expose private runtime values;
- store secret values;
- change retention settings;
- delete production records;
- approve production launch;
- schedule production launch;
- publish compliance material;
- render compliance material;
- bypass workflow gates.

## Privacy evidence categories

The index must cover privacy evidence for:

- data handling controls;
- evidence retention controls;
- support note handling;
- incident note handling;
- customer data export restrictions;
- private runtime value exclusions;
- redaction and replacement decisions;
- deletion route decisions;
- owner and reviewer sign-off;
- privacy stop conditions;
- compliance closeout evidence.

## Evidence classes

Allowed evidence classes:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized privacy review note;
- summarized retention decision;
- summarized deletion route note;
- summarized redaction note;
- summarized owner review note;
- summarized support privacy note;
- summarized incident privacy note;
- evidence archive entry name.

Forbidden evidence classes:

- customer data export;
- private runtime value;
- secret value;
- raw credential;
- production token;
- private environment dump;
- raw log with restricted value;
- raw support transcript with private data;
- raw incident dump with private data;
- screenshot containing restricted value;
- external package export.

## Required evidence fields

Each privacy compliance evidence item must record:

- evidence item identifier;
- privacy control area;
- source document;
- source issue or PR;
- owner;
- reviewer;
- evidence class;
- evidence sensitivity;
- retention decision;
- deletion route when applicable;
- redaction status;
- review cadence;
- escalation route;
- action owner;
- validation requirement;
- closure criteria.

## Privacy control mapping

Privacy control areas must map to:

- allowed data handling;
- prohibited data handling;
- data category review;
- retention decisions;
- evidence sensitivity classes;
- log handling rules;
- support and incident note rules;
- export rules;
- deletion or replacement routes;
- privacy stop conditions.

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

Restricted value suspected, restricted value confirmed, customer data suspected, and customer data confirmed require escalation.

## Retention linkage

Each privacy evidence item must link to one retention decision:

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

Retention linkage must not authorize customer data export.

## Review cadence

Review cadence options:

- per PR closeout;
- before compliance closeout;
- after support pattern;
- after incident signal;
- after retention rule change;
- after privacy stop condition;
- monthly during steady operation.

## Escalation routes

Escalate privacy evidence when:

- owner is missing;
- reviewer is missing;
- evidence sensitivity is unclear;
- restricted value is suspected;
- restricted value is confirmed;
- customer data is suspected;
- customer data is confirmed;
- deletion route is missing when replacement is required;
- retention decision is missing;
- export request appears;
- workflow gate bypass is requested.

## Stop conditions

Stop privacy evidence index closure if:

- evidence item identifier is missing;
- privacy control area is missing;
- source document is missing;
- source issue or PR is missing;
- owner is missing;
- reviewer is missing;
- evidence class is missing;
- evidence sensitivity is missing;
- retention decision is missing;
- redaction status is missing when restricted value is suspected;
- deletion route is missing when evidence must be replaced;
- escalation route is missing for suspected customer data;
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
tests/integration/test_p20_step_01.py
```

The validation checks source references, documentation-only status, privacy evidence categories, evidence classes, required fields, privacy control mapping, sensitivity classes, retention linkage, review cadence, escalation routes, stop conditions, guardrails, and P20 CI wildcard coverage.
