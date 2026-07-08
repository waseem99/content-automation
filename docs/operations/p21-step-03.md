# P21 Step 03

This step documents rollback and restore evidence review for production operational drill and recovery readiness.

Part of #287. Closes #290 after the PR merges.

## Goal

Define documentation-only rollback and restore evidence review so operators can evaluate recovery decisions without implying live rollback, live restore, production data changes, or production launch approval.

## Source references

This review builds on:

```text
docs/operations/p21-step-01.md
docs/operations/p21-step-02.md
docs/operations/p20-step-03.md
docs/operations/p20-readiness-report.md
docs/operations/p19-step-03.md
docs/operations/p19-step-05.md
docs/operations/p17-step-02.md
docs/operations/p17-step-05.md
```

## Review status

This rollback and restore evidence review is documentation-only.

It does not:

- execute rollback;
- execute restore;
- restore production data;
- change production configuration;
- approve rollback;
- approve restore;
- approve production launch;
- schedule recovery activity;
- bypass workflow gates;
- export restricted evidence.

## Decision evidence areas

The review must cover:

- rollback decision question;
- restore decision question;
- release owner review;
- incident owner review;
- evidence owner review;
- affected scope summary;
- validation expectation;
- rollback route placeholder;
- restore route placeholder;
- follow-up issue route;
- closure criteria.

## Required evidence fields

Each rollback/restore evidence item must record:

- evidence item identifier;
- decision type;
- simulated scenario;
- affected scope summary;
- decision owner;
- release owner;
- incident owner when applicable;
- evidence owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- validation requirement;
- rollback route placeholder;
- restore route placeholder;
- follow-up route;
- approval status;
- closure criteria.

## Approval status values

Allowed approval status values:

- not approved;
- review only;
- decision pending;
- approved placeholder only;
- rejected with reason;
- blocked;
- blocked by guardrail.

No status may imply live rollback or live restore.

## Validation expectations

Validation must confirm:

- exact-head CI evidence is referenced when implementation is involved;
- affected scope is summarized;
- owner review is documented;
- evidence sensitivity is documented;
- restricted values are not retained;
- rollback and restore are not executed;
- follow-up issue is created when implementation is needed.

## Evidence rules

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized rollback review note;
- summarized restore review note;
- summarized owner review note;
- summarized validation note;
- evidence archive entry name.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- customer data exports;
- external package exports;
- raw logs with restricted values;
- production data dumps;
- rendered rollback material;
- scheduled restore outputs.

## Stop conditions

Stop rollback/restore evidence closure if:

- evidence item identifier is missing;
- decision type is missing;
- affected scope summary is missing;
- decision owner is missing;
- release owner is missing for rollback or restore decision;
- evidence owner is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- validation requirement is missing;
- approval status is missing;
- live rollback is implied;
- live restore is implied;
- production data restore is implied;
- production change is implied;
- secret value is present;
- private runtime value is present;
- customer data export is requested;
- external export is requested;
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
tests/integration/test_p21_step_03.py
```

The validation checks source references, documentation-only status, decision evidence areas, required fields, approval status values, validation expectations, evidence rules, stop conditions, and guardrails.
