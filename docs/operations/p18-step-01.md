# P18 Step 01

This step documents the operator handover guide for production handover and operator enablement.

Part of #248. Closes #249 after the PR merges.

## Goal

Create an operator-friendly entry point that explains how to understand, operate, review, escalate, and safely hand over the system without bypassing release, observability, evidence, or support guardrails.

## Source references

This handover guide builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p14-step-06.md
docs/operations/p15-readiness-report.md
docs/operations/p16-readiness-report.md
docs/operations/p17-readiness-report.md
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p17-step-03.md
docs/operations/p17-step-04.md
docs/operations/p17-step-05.md
```

## Handover status

This guide is documentation-only.

It does not:

- approve production launch;
- schedule production launch;
- execute release activities;
- grant automatic approval;
- bypass workflow gates;
- publish operator material;
- render training material;
- export handover evidence;
- replace role-based procedures;
- replace support escalation.

## Operator orientation

Operators must understand:

- current phase context;
- parent epic and child issue workflow;
- branch naming rules;
- PR title and body rules;
- exact-head CI requirement;
- release calendar requirement;
- blackout window requirement;
- manual approval requirement;
- evidence safety rules;
- escalation routes;
- stop conditions.

## Required operating context

Before operating the system, an operator must review:

- production compliance context;
- continuous improvement context;
- observability context;
- release readiness context;
- current open issue list;
- current open PR list;
- latest readiness report;
- latest closeout checklist;
- latest exact-head CI evidence;
- active guardrails.

## Safe operating principles

Operators must follow these principles:

- work from a scoped issue;
- create a branch from `test`;
- keep PR scope limited;
- use exact PR title and body format;
- wait for exact-head CI;
- patch failures on the same branch;
- merge only after required checks are green;
- confirm issue closure after merge;
- update parent epic evidence during closeout;
- capture CI evidence from the final exact branch head;
- never store restricted values in evidence.

## Daily checks

Daily operator checks should include:

- open issues review;
- open PR review;
- required workflow status review;
- failed CI review;
- blocked issue review;
- evidence sensitivity review;
- support signal review;
- incident signal review;
- documentation freshness review;
- next-action owner review.

## Evidence handling

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized operator notes;
- summarized support notes;
- summarized incident notes;
- summarized readiness notes;
- summarized closeout notes;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- raw logs with restricted values;
- rendered operator materials;
- scheduled handover outputs.

## Escalation routes

Escalate when:

- exact-head CI fails;
- issue scope is unclear;
- PR scope expands;
- release decision is requested;
- blackout window conflict appears;
- manual approval is missing;
- evidence contains restricted values;
- incident signal appears;
- support case requires owner;
- owner is missing;
- reviewer is missing;
- workflow gate bypass is requested.

## Operator handover fields

Each operator handover entry must record:

- handover item identifier;
- handover area;
- required context;
- operator owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- daily check requirement;
- escalation route;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Action routes

Allowed action routes:

- no action required;
- update operator handover guide;
- update role-based procedure;
- update training checklist;
- update support playbook;
- update runbook ownership map;
- create implementation issue;
- request more evidence;
- escalate to release owner;
- escalate to support owner;
- block by guardrail;
- reject with reason.

## Stop conditions

Stop handover closure if:

- operator owner is missing;
- reviewer is missing;
- required context is missing;
- evidence source is missing;
- escalation route is missing;
- daily checks are missing;
- action owner is missing for required action;
- exact-head CI evidence is missing for implementation;
- release approval is implied;
- production launch is implied;
- workflow gate bypass is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- customer data export is requested;
- external export is requested.

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
tests/integration/test_p18_step_01.py
```

The validation checks source references, documentation-only status, operator orientation, required context, safe operating principles, daily checks, evidence handling, escalation routes, handover fields, action routes, stop conditions, guardrails, and P18 CI wildcard coverage.
