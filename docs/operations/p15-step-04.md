# P15 Step 04

This step documents support and incident trend review expectations for production continuous improvement and optimization.

Part of #209. Closes #213 after the PR merges.

## Goal

Create a repeatable review process for converting repeated support questions, incidents, operational friction, repeated alerts, and action tracker patterns into runbook updates, backlog items, or product fixes.

## Source references

This runbook builds on:

```text
docs/operations/p15-step-01.md
docs/operations/p15-step-02.md
docs/operations/p15-step-03.md
docs/operations/p14-readiness-report.md
```

## Trend inputs

Each trend review must inspect:

- incident review notes;
- support question patterns;
- operational friction reports;
- repeated alert patterns;
- failed or delayed action tracker items;
- manual workaround reports;
- runbook confusion reports;
- access review follow-up items;
- control testing follow-up items;
- cost and performance review actions;
- audit readiness observations;
- CI and validation failure patterns.

## Trend categories

Classify each trend as one of:

- incident recurrence;
- support recurrence;
- alert recurrence;
- manual workaround recurrence;
- runbook gap;
- ownership gap;
- validation gap;
- evidence gap;
- access review gap;
- control testing gap;
- performance or cost trend;
- product fix candidate.

## Required review fields

Each trend item must record:

- trend identifier;
- trend category;
- source evidence;
- first observed date;
- latest observed date;
- occurrence count;
- impact summary;
- owner;
- reviewer;
- action route;
- action owner;
- validation requirement;
- evidence requirement;
- linked backlog item, issue, or PR when applicable;
- closure decision.

## Review cadence

Run trend review:

- after a material incident;
- during monthly production improvement review;
- before P15 closeout;
- when repeated support patterns are observed;
- when repeated alerts are observed;
- when action tracker delays repeat.

## Action routing

Allowed action routes:

- update runbook;
- create backlog item;
- create implementation issue;
- update alert routing;
- update ownership record;
- update validation evidence;
- request more evidence;
- accept as known limitation with owner and expiry;
- reject with reason;
- block by guardrail.

## Ownership expectations

Required ownership:

- trend owner;
- reviewer;
- action owner for routed actions;
- validation owner when implementation is recommended;
- evidence owner for each evidence source;
- escalation owner for high-impact or repeated trends.

Critical or repeated trends cannot close without an action owner and evidence.

## Closure criteria

Trend closure requires:

- source evidence;
- owner and reviewer;
- action route;
- action owner when action is required;
- validation result when implementation occurred;
- linked backlog item, issue, or PR when implementation occurred;
- evidence archive entry;
- closure decision;
- no unresolved guardrail conflict.

## Stop conditions

Stop closure if:

- source evidence is missing;
- owner is missing;
- reviewer is missing;
- action route is missing;
- action owner is missing for required action;
- validation requirement is missing for implementation work;
- repeated or critical trend has no action owner;
- repeated or critical trend has no evidence;
- item contains secret values;
- item contains private runtime values;
- workflow gate bypass is requested;
- automatic approval is requested;
- permanent exception is requested.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No critical or repeated trend closure without action owner.
- No critical or repeated trend closure without evidence.
- No permanent exceptions.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p15_step_04.py
```

The validation checks source references, trend inputs, trend categories, required fields, review cadence, action routing, ownership expectations, closure criteria, stop conditions, and guardrails.
