# P15 Step 03

This step documents cost and performance review expectations for production continuous improvement and optimization.

Part of #209. Closes #212 after the PR merges.

## Goal

Create a repeatable review process for identifying cost, runtime performance, storage growth, and operational bottleneck improvements without exposing restricted data or bypassing production controls.

## Source references

This runbook builds on:

```text
docs/operations/p15-step-01.md
docs/operations/p15-step-02.md
docs/operations/p14-readiness-report.md
```

## Review inputs

Each review must inspect:

- infrastructure cost signals;
- runtime performance signals;
- database performance signals;
- object storage growth signals;
- queue or worker throughput signals;
- API latency signals;
- error-rate trends;
- capacity planning evidence;
- alert noise indicators;
- operator time spent on manual steps;
- optimization backlog items;
- prior action outcomes.

## Required review fields

Each cost and performance review must record:

- review identifier;
- review date;
- cost owner;
- performance owner;
- evidence owner;
- reviewer;
- signal source;
- observed trend;
- expected impact;
- risk level;
- recommended action;
- action owner;
- target review date;
- validation requirement;
- evidence archive entry;
- closure status.

## Evidence rules

Allowed evidence includes:

- aggregated cost trend references;
- summarized latency metrics;
- summarized error-rate trends;
- storage growth summaries;
- queue and worker throughput summaries;
- CI run identifiers;
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

## Review decisions

Allowed decisions:

- no action required;
- optimization backlog item required;
- implementation issue required;
- more evidence required;
- capacity review required;
- documentation update required;
- blocked by guardrail;
- rejected with reason.

## Ownership expectations

Required ownership:

- cost owner for cost-related findings;
- performance owner for runtime findings;
- evidence owner for each evidence source;
- action owner for each recommended action;
- reviewer for closure decision;
- validation owner when implementation is recommended.

Ownerless findings cannot close as complete.

## Action tracking

Each recommended action must record:

- action summary;
- action owner;
- target review date;
- validation requirement;
- evidence required for closure;
- linked backlog item, issue, or PR when applicable;
- final reviewer decision.

## Closure criteria

A review item can close only when:

- evidence source is recorded;
- owner and reviewer are recorded;
- recommended action has an owner;
- validation result is recorded when implementation occurred;
- linked issue or PR is recorded when implementation occurred;
- evidence archive entry is recorded;
- no restricted value is included;
- no external export is requested.

## Stop conditions

Stop closure if:

- cost owner is missing for cost finding;
- performance owner is missing for performance finding;
- evidence source is missing;
- reviewer is missing;
- action owner is missing;
- validation requirement is missing for implementation work;
- item contains secret values;
- item contains private runtime values;
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
tests/integration/test_p15_step_03.py
```

The validation checks source references, review inputs, required fields, evidence rules, review decisions, ownership expectations, action tracking, closure criteria, stop conditions, and guardrails.
