# P22 Step 05

This step documents data export and sharing guardrails for production privacy and data-governance readiness.

Part of #300. Closes #305 after the PR merges.

## Goal

Define which export and sharing requests are allowed, which materials are prohibited, which approval routes apply, how redaction must work, and what stops closure.

## Source references

This guardrail set builds on:

```text
docs/operations/p22-step-01.md
docs/operations/p22-step-03.md
docs/operations/p20-step-03.md
docs/operations/p20-step-05.md
docs/operations/p19-step-03.md
docs/operations/p19-step-04.md
docs/operations/p21-readiness-report.md
```

## Guardrail status

This data export and sharing guardrail set is documentation-only.

It does not:

- export customer data;
- export external packages;
- send customer communication;
- share restricted screenshots;
- publish handoff materials;
- render export materials;
- schedule sharing activity;
- approve production launch;
- bypass workflow gates;
- replace owner review.

## Export and sharing types

The guardrails cover:

- customer data export;
- external package export;
- report sharing;
- screenshot sharing;
- handoff material sharing;
- evidence archive reference sharing;
- CI evidence reference sharing;
- audit note sharing;
- support note sharing;
- incident note sharing;
- drill note sharing.

## Allowed sharing forms

Allowed sharing forms:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- evidence archive entry name;
- summarized non-sensitive note;
- redacted summary;
- owner-reviewed summary;
- reviewer-approved summary.

## Prohibited materials

Do not share:

- customer data;
- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- raw logs with restricted values;
- screenshots containing restricted values;
- raw support transcripts with private data;
- raw incident dumps with private data;
- package bundle exports;
- raw dependency archives;
- private package artifacts;
- external package exports;
- real phone numbers;
- private email addresses;
- customer identifiers.

## Approval routes

Allowed approval routes:

- no export required;
- approve summary-only sharing;
- approve redacted summary;
- request redaction;
- reject with reason;
- route to data owner;
- route to evidence owner;
- route to privacy owner;
- route to security incident response;
- route to dependency owner;
- route to support owner;
- block by guardrail.

## Redaction rules

Redaction must:

- remove exact restricted values;
- replace values with named placeholders;
- preserve enough non-sensitive context for review;
- record redaction owner;
- record redaction reason;
- record evidence sensitivity after redaction;
- route suspected exposure to security incident response;
- block closeout if redaction cannot be confirmed.

## Required sharing fields

Each sharing review item must record:

- sharing item identifier;
- sharing type;
- source location;
- data class;
- sensitivity level;
- intended recipient category placeholder;
- allowed sharing form;
- prohibited material status;
- owner;
- reviewer;
- approval route;
- redaction status;
- evidence source;
- escalation route;
- validation requirement;
- closure criteria.

## Stop conditions

Stop sharing closure if:

- sharing item identifier is missing;
- sharing type is missing;
- source location is missing;
- data class is missing;
- sensitivity level is missing;
- intended recipient category placeholder is missing;
- allowed sharing form is missing;
- prohibited material status is missing;
- owner is missing;
- reviewer is missing;
- approval route is missing;
- redaction status is missing when redaction is required;
- customer data export is requested;
- external package export is requested;
- package bundle export is requested;
- screenshot contains restricted value;
- real contact detail is present;
- customer identifier is present;
- secret value is present;
- private runtime value is present;
- external communication is implied;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic export.
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
tests/integration/test_p22_step_05.py
```

The validation checks source references, documentation-only status, export and sharing types, allowed sharing forms, prohibited materials, approval routes, redaction rules, required fields, stop conditions, and guardrails.
