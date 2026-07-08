# P17 Step 01

This step documents the release decision pack for controlled production release readiness.

Part of #235. Closes #236 after the PR merges.

## Goal

Create a manual release decision pack that converts P16 observability into safe release decision inputs without launching, scheduling, publishing, rendering, or exporting production materials.

## Source references

This runbook builds on:

```text
docs/operations/p16-readiness-report.md
docs/operations/p16-closeout-checklist.md
docs/operations/p16-step-01.md
docs/operations/p16-step-02.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
```

## Decision pack status

This phase is documentation-only.

The release decision pack does not:

- approve a production launch;
- schedule a production launch;
- publish a public release note;
- render release materials;
- export release evidence;
- bypass workflow gates;
- replace human approval.

## Required sections

The release decision pack must include:

- release identifier;
- release scope summary;
- release candidate reference;
- readiness summary;
- observability readiness summary;
- open blocker summary;
- known risk summary;
- dependency summary;
- rollback readiness summary;
- migration readiness summary;
- monitoring readiness summary;
- evidence summary;
- decision owner summary;
- manual approval requirement;
- go/no-go handoff summary.

## Readiness signals

Use these readiness signals:

- exact-head CI status;
- release checklist status;
- dry-run rehearsal status;
- migration readiness status;
- rollback readiness status;
- monitoring readiness status;
- alert quality status;
- service level risk status;
- metrics evidence status;
- documentation freshness status;
- incident trend status;
- unresolved blocker status.

## Required decision fields

Each decision item must record:

- decision item identifier;
- decision area;
- readiness signal;
- source evidence;
- evidence sensitivity;
- owner;
- reviewer;
- status;
- blocker status;
- risk status;
- dependency status;
- action route;
- action owner;
- approval requirement;
- closure criteria.

## Decision statuses

Allowed statuses:

- ready for review;
- ready with notes;
- blocked;
- deferred;
- needs owner;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## Action routes

Allowed action routes:

- no action required;
- update release decision pack;
- update production release checklist;
- update dry-run rehearsal process;
- update go/no-go approval record;
- update post-release observation plan;
- update monitoring readiness;
- update rollback readiness;
- create implementation issue;
- request more evidence;
- block by guardrail;
- reject with reason.

## Human decision requirements

The release decision pack must require:

- named decision owner;
- named reviewer;
- manual go/no-go approval record;
- rollback readiness confirmation;
- monitoring readiness confirmation;
- blackout check confirmation;
- release calendar confirmation;
- unresolved blocker disposition;
- exact-head CI evidence.

Release decision pack completion does not authorize launch.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized readiness notes;
- summarized observability notes;
- summarized blocker notes;
- summarized risk notes;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- rendered release materials;
- scheduled release outputs.

## Stop conditions

Stop release decision closure if:

- decision owner is missing;
- reviewer is missing;
- source evidence is missing;
- manual approval requirement is missing;
- unresolved blocker has no disposition;
- rollback readiness is missing;
- monitoring readiness is missing;
- blackout check is missing;
- calendar confirmation is missing;
- exact-head CI evidence is missing;
- approval is automatic;
- public launch is implied;
- workflow gate bypass is requested;
- release evidence contains secret values;
- release evidence contains private runtime values;
- external export is requested.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No public production launch without explicit decision.
- No release without calendar entry.
- No release during blackout window.
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
tests/integration/test_p17_step_01.py
```

The validation checks source references, documentation-only status, required sections, readiness signals, decision fields, statuses, action routes, human decision requirements, evidence rules, stop conditions, guardrails, and P17 CI wildcard coverage.
