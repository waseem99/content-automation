# P16 Step 01

This step documents the production health metrics catalog for observability and operating metrics.

Part of #222. Closes #223 after the PR merges.

## Goal

Create a safe, reviewable catalog of production health signals that operators can use to understand system health without exporting restricted values or bypassing governance controls.

## Source references

This runbook builds on:

```text
docs/operations/p15-readiness-report.md
docs/operations/p15-closeout-checklist.md
docs/operations/p15-step-01.md
docs/operations/p15-step-03.md
docs/operations/p15-step-04.md
docs/operations/p15-step-05.md
```

## Core health signals

Track production health through these metric groups:

- CI health;
- workflow duration;
- workflow failure rate;
- queue health;
- worker success rate;
- worker failure rate;
- retry volume;
- database migration health;
- database latency trend;
- API latency trend;
- storage growth trend;
- object processing volume;
- error-rate trend;
- alert volume trend;
- support trend volume;
- incident recurrence trend;
- documentation freshness trend;
- operator manual effort trend.

## Required metric fields

Each metric entry must record:

- metric identifier;
- metric group;
- metric description;
- signal source;
- owner;
- reviewer;
- review cadence;
- expected direction;
- threshold or review trigger;
- evidence source;
- evidence sensitivity;
- action route;
- validation requirement;
- retention reference;
- closure criteria.

## Review cadence

Review cadence may be:

- per pull request;
- per release readiness review;
- weekly operations review;
- monthly production health review;
- after material incident;
- before phase closeout.

Every metric must have one cadence and one owner.

## Evidence rules

Allowed evidence includes:

- CI run identifiers;
- summarized workflow duration notes;
- summarized queue health notes;
- summarized worker success or failure notes;
- summarized latency trends;
- summarized error-rate trends;
- summarized storage growth notes;
- issue or PR references;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports.

## Action routes

Metric review can route actions to:

- no action required;
- operational improvement backlog;
- alert quality review;
- service level review;
- metrics evidence retention review;
- documentation freshness review;
- implementation issue required;
- more evidence required;
- blocked by guardrail;
- rejected with reason.

## Ownership expectations

Required ownership:

- metric owner;
- reviewer;
- evidence owner;
- action owner when action is required;
- validation owner when implementation is recommended;
- escalation owner for repeated or high-impact degradation.

Ownerless metrics cannot close as reviewed.

## Stop conditions

Stop metric closure if:

- metric owner is missing;
- reviewer is missing;
- signal source is missing;
- evidence source is missing;
- review cadence is missing;
- threshold or review trigger is missing;
- action owner is missing for required action;
- metric contains secret values;
- metric contains private runtime values;
- external export is requested;
- workflow gate bypass is requested;
- automatic approval is requested.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
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
tests/integration/test_p16_step_01.py
```

The validation checks source references, core health signals, required metric fields, review cadence, evidence rules, action routes, ownership expectations, stop conditions, guardrails, and P16 CI wildcard coverage.
