# P22 Step 01

This step documents the data classification and handling map for production privacy and data-governance readiness.

Part of #300. Closes #301 after the PR merges.

## Goal

Define what data classes may appear in operational evidence, how each class must be handled, which roles own review, and which values must never be stored in issues, PRs, runbooks, drill records, or closeout evidence.

## Source references

This map builds on:

```text
docs/operations/p21-readiness-report.md
docs/operations/p20-step-01.md
docs/operations/p20-step-04.md
docs/operations/p19-step-03.md
docs/operations/p19-step-01.md
docs/operations/p18-step-01.md
docs/operations/p18-step-05.md
docs/operations/p16-step-05.md
```

## Map status

This data classification and handling map is documentation-only.

It does not:

- collect production data;
- export customer data;
- expose private runtime values;
- store secret values;
- change retention settings;
- approve production launch;
- schedule production launch;
- publish data maps;
- render data maps;
- bypass workflow gates.

## Data classes

Allowed data classes for evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- public configuration name;
- non-sensitive status summary;
- summarized operator note;
- summarized support note;
- summarized incident note;
- summarized audit note;
- summarized drill note;
- evidence archive entry name.

Restricted data classes:

- customer data;
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

## Sensitivity levels

Allowed sensitivity levels:

- public reference;
- internal summary;
- restricted summary;
- restricted value suspected;
- restricted value confirmed;
- customer data suspected;
- customer data confirmed;
- blocked by guardrail.

Restricted value suspected, restricted value confirmed, customer data suspected, and customer data confirmed require escalation and cannot be closed without owner review.

## Handling rules

Handling rules must define:

- allowed summary form;
- prohibited raw form;
- owner role;
- reviewer role;
- evidence sensitivity;
- retention decision;
- deletion or replacement route;
- escalation route;
- validation requirement;
- closure criteria.

## Prohibited storage

Do not store:

- actual customer data;
- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- raw logs with restricted values;
- screenshots containing restricted values;
- external package exports;
- rendered data materials;
- scheduled data outputs.

## Ownership roles

Required roles:

- data owner;
- evidence owner;
- operator owner;
- support owner;
- incident owner;
- release owner;
- reviewer;
- documentation owner.

## Review cadence

Review cadence options:

- per PR closeout;
- before privacy closeout;
- after support pattern;
- after incident signal;
- after drill finding;
- after data handling change;
- monthly during steady operation.

## Required classification fields

Each classification item must record:

- classification item identifier;
- data class;
- sensitivity level;
- source location;
- allowed handling summary;
- prohibited storage rule;
- owner;
- reviewer;
- retention decision;
- deletion or replacement route;
- escalation route;
- review cadence;
- validation requirement;
- closure criteria.

## Stop conditions

Stop classification closure if:

- classification item identifier is missing;
- data class is missing;
- sensitivity level is missing;
- source location is missing;
- owner is missing;
- reviewer is missing;
- retention decision is missing;
- prohibited storage rule is missing;
- deletion or replacement route is missing when restricted data is suspected;
- escalation route is missing for restricted or customer data;
- customer data export is requested;
- secret value is present;
- private runtime value is present;
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
tests/integration/test_p22_step_01.py
```

The validation checks source references, documentation-only status, data classes, sensitivity levels, handling rules, prohibited storage, ownership roles, review cadence, required fields, stop conditions, guardrails, and P22 CI wildcard coverage.
