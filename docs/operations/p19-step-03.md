# P19 Step 03

This step documents data handling and retention review controls for production privacy readiness.

Part of #261. Closes #264 after the PR merges.

## Goal

Define allowed data, prohibited data, evidence sensitivity, retention decisions, deletion routes, escalation routes, and stop conditions for logs, evidence, support notes, incident notes, and exports.

## Source references

This privacy review builds on:

```text
docs/operations/p19-step-01.md
docs/operations/p19-step-02.md
docs/operations/p18-step-04.md
docs/operations/p18-step-05.md
docs/operations/p17-step-05.md
docs/operations/p16-step-05.md
docs/operations/p14-step-06.md
```

## Review status

This data handling review is documentation-only.

It does not:

- collect production data;
- export customer data;
- publish retention material;
- render privacy material;
- change retention settings;
- delete production records;
- approve production launch;
- schedule production launch;
- bypass workflow gates;
- replace incident escalation.

## Allowed data handling

Allowed evidence may include:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized support notes;
- summarized incident notes;
- summarized retention notes;
- summarized privacy review notes;
- evidence archive entry names;
- owner and reviewer role names;
- non-sensitive status summaries.

## Prohibited data handling

Prohibited data includes:

- customer data exports;
- private runtime values;
- secret values;
- raw credentials;
- production tokens;
- private environment dumps;
- raw logs with restricted values;
- raw support transcripts with private data;
- raw incident dumps with private data;
- external package exports;
- personal data copied into closeout notes;
- sensitive operational values copied into issues.

## Data category review

Each data category must define:

- data category identifier;
- data source;
- allowed summary form;
- prohibited raw form;
- sensitivity classification;
- retention decision;
- owner;
- reviewer;
- deletion route;
- escalation route;
- evidence expectation;
- closure criteria.

## Retention decisions

Allowed retention decisions:

- retain summary only;
- retain issue or PR reference only;
- retain CI run identifier only;
- retain evidence archive entry name only;
- redact and retain summary;
- reject evidence;
- delete or replace evidence;
- escalate to evidence owner;
- escalate to security incident response;
- block by guardrail.

Retention decisions must not authorize customer data export.

## Evidence sensitivity classes

Allowed sensitivity classes:

- public reference;
- internal summary;
- restricted summary;
- restricted value suspected;
- restricted value confirmed;
- customer data suspected;
- customer data confirmed;
- blocked by guardrail.

## Log handling rules

Log handling must follow these rules:

- retain summarized log notes only;
- avoid raw log dumps in issues;
- redact restricted values before notes are retained;
- route suspected restricted values to evidence owner;
- route confirmed exposure to security incident response;
- block external export of raw logs;
- record source reference without copying private values.

## Support and incident note rules

Support and incident notes must:

- summarize the case without private data;
- avoid customer identifiers when not required;
- avoid raw transcript copying;
- avoid screenshots containing restricted values;
- include owner and reviewer roles;
- include evidence sensitivity;
- include escalation route when privacy risk is suspected;
- include follow-up issue when implementation is required.

## Export rules

Exports are blocked unless they are documented as:

- issue or PR reference only;
- CI run identifier only;
- merge commit reference only;
- evidence archive entry name only;
- summarized non-sensitive notes.

Customer data exports and external package exports remain prohibited.

## Required review fields

Each data handling review item must record:

- review item identifier;
- data category;
- source location;
- owner;
- reviewer;
- sensitivity class;
- retention decision;
- redaction status;
- deletion route;
- escalation route;
- evidence source;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Stop conditions

Stop data review closure if:

- data category is missing;
- owner is missing;
- reviewer is missing;
- sensitivity class is missing;
- retention decision is missing;
- evidence source is missing;
- redaction status is missing when restricted value is suspected;
- deletion route is missing when evidence must be replaced;
- escalation route is missing when privacy risk is suspected;
- customer data export is requested;
- private runtime value is present;
- secret value is present;
- raw credential is present;
- production token is present;
- external package export is requested;
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
tests/integration/test_p19_step_03.py
```

The validation checks source references, documentation-only status, allowed data handling, prohibited data handling, data category review, retention decisions, sensitivity classes, log rules, support and incident note rules, export rules, required fields, stop conditions, and guardrails.
