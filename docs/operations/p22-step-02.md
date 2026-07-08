# P22 Step 02

This step documents the retention and deletion policy for production privacy and data-governance readiness.

Part of #300. Closes #302 after the PR merges.

## Goal

Define retention windows, deletion triggers, archive rules, replacement routes, deletion evidence records, owner review, and stop conditions while keeping evidence summary-only and restricted-value safe.

## Source references

This policy builds on:

```text
docs/operations/p22-step-01.md
docs/operations/p20-step-04.md
docs/operations/p20-readiness-report.md
docs/operations/p19-step-03.md
docs/operations/p16-step-05.md
docs/operations/p18-step-05.md
```

## Policy status

This retention and deletion policy is documentation-only.

It does not:

- delete production records;
- change retention settings;
- collect production data;
- export customer data;
- store restricted values;
- approve production launch;
- schedule deletion jobs;
- publish retention evidence;
- render retention evidence;
- bypass workflow gates.

## Retention windows

Allowed retention windows:

- retain issue or PR reference only;
- retain CI run identifier only;
- retain merge commit reference only;
- retain evidence archive entry name only;
- retain summary until phase closeout;
- retain summary until owner review;
- retain summary until replacement evidence is recorded;
- reject evidence immediately;
- delete or replace evidence immediately;
- block by guardrail.

## Deletion triggers

Deletion or replacement is triggered when:

- customer data is suspected;
- customer data is confirmed;
- secret value is suspected;
- secret value is confirmed;
- private runtime value is suspected;
- restricted value appears in notes;
- raw credential appears;
- production token appears;
- raw log contains restricted value;
- screenshot contains restricted value;
- evidence is not summary-only.

## Archive rules

Archive entries may include only:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized owner note;
- summarized reviewer note;
- summarized deletion note;
- summarized replacement note;
- evidence archive entry name.

Archive entries must not include customer data, secret values, private runtime values, raw credentials, production tokens, raw logs, or screenshots containing restricted values.

## Replacement routes

Allowed replacement routes:

- replace with issue or PR reference;
- replace with CI run identifier;
- replace with merge commit reference;
- replace with summarized non-sensitive note;
- replace with evidence archive entry name;
- route to evidence owner;
- route to privacy owner;
- route to security incident response;
- create documentation issue;
- create implementation issue;
- block by guardrail.

## Required deletion evidence fields

Each deletion evidence record must include:

- deletion evidence identifier;
- source location;
- data class;
- sensitivity level;
- deletion trigger;
- retention window;
- replacement route;
- owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- deletion status;
- validation requirement;
- closure criteria.

## Deletion statuses

Allowed deletion statuses:

- not required;
- replacement required;
- replaced with summary;
- rejected with reason;
- owner review required;
- incident escalation required;
- blocked;
- blocked by guardrail.

## Owner review

Owner review must confirm:

- data class is recorded;
- sensitivity level is recorded;
- retention window is valid;
- deletion trigger is recorded when applicable;
- replacement route is recorded when applicable;
- evidence is summary-only;
- restricted values are not retained;
- closure criteria are met.

## Stop conditions

Stop policy closure if:

- deletion evidence identifier is missing;
- source location is missing;
- data class is missing;
- sensitivity level is missing;
- retention window is missing;
- owner is missing;
- reviewer is missing;
- deletion status is missing;
- replacement route is missing when replacement is required;
- evidence source is missing;
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
- No automatic deletion.
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
tests/integration/test_p22_step_02.py
```

The validation checks source references, documentation-only status, retention windows, deletion triggers, archive rules, replacement routes, required fields, deletion statuses, owner review, stop conditions, and guardrails.
