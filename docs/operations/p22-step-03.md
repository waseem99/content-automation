# P22 Step 03

This step documents the privacy-safe evidence checklist for production privacy and data-governance readiness.

Part of #300. Closes #303 after the PR merges.

## Goal

Ensure operational evidence surfaces such as logs, CI evidence, audit notes, support notes, drill records, and closeout records remain summary-only and do not expose secrets, private runtime values, customer data, or other restricted values.

## Source references

This checklist builds on:

```text
docs/operations/p22-step-01.md
docs/operations/p22-step-02.md
docs/operations/p21-readiness-report.md
docs/operations/p20-step-03.md
docs/operations/p20-step-04.md
docs/operations/p19-step-01.md
docs/operations/p19-step-03.md
docs/operations/p16-step-05.md
```

## Checklist status

This privacy-safe evidence checklist is documentation-only.

It does not:

- collect production data;
- export customer data;
- expose secret values;
- expose private runtime values;
- publish evidence;
- render evidence;
- schedule evidence reviews;
- approve production launch;
- bypass workflow gates;
- replace owner review.

## Evidence surfaces

The checklist covers:

- CI evidence;
- workflow logs;
- audit notes;
- support notes;
- incident notes;
- drill records;
- closeout reports;
- readiness reports;
- PR comments;
- issue comments;
- screenshots;
- handoff materials.

## Allowed evidence summaries

Allowed summaries:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized log note;
- summarized support note;
- summarized incident note;
- summarized audit note;
- summarized drill note;
- summarized reviewer note;
- evidence archive entry name.

## Prohibited values

Do not store:

- customer data;
- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- raw logs with restricted values;
- raw support transcripts with private data;
- raw incident dumps with private data;
- screenshots containing restricted values;
- private email addresses;
- real phone numbers;
- external package exports.

## Review rules

Each evidence review must confirm:

- evidence surface is identified;
- allowed summary form is used;
- prohibited value scan is complete;
- evidence owner is recorded;
- reviewer is recorded;
- evidence sensitivity is recorded;
- retention decision is recorded;
- deletion or replacement route is recorded when required;
- escalation route is recorded when required;
- closure criteria are met.

## Required checklist fields

Each checklist item must record:

- checklist item identifier;
- evidence surface;
- allowed summary form;
- prohibited value status;
- evidence owner;
- reviewer;
- evidence sensitivity;
- retention decision;
- deletion or replacement route;
- escalation route;
- validation requirement;
- closure criteria.

## Escalation routes

Escalate when:

- prohibited value is suspected;
- prohibited value is confirmed;
- evidence sensitivity is unclear;
- customer data is suspected;
- customer data is confirmed;
- screenshot contains restricted value;
- raw transcript contains private data;
- evidence owner is missing;
- reviewer is missing;
- workflow gate bypass is requested.

## Stop conditions

Stop checklist closure if:

- checklist item identifier is missing;
- evidence surface is missing;
- allowed summary form is missing;
- prohibited value status is missing;
- evidence owner is missing;
- reviewer is missing;
- evidence sensitivity is missing;
- retention decision is missing;
- prohibited value remains in evidence;
- deletion or replacement route is missing when required;
- escalation route is missing when required;
- customer data export is requested;
- secret value is present;
- private runtime value is present;
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
tests/integration/test_p22_step_03.py
```

The validation checks source references, documentation-only status, evidence surfaces, allowed summaries, prohibited values, review rules, required fields, escalation routes, stop conditions, and guardrails.
