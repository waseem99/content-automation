# P16 Step 02

This step documents operational dashboard requirements for production observability and operating metrics.

Part of #222. Closes #224 after the PR merges.

## Goal

Define what operators should be able to review in an operational dashboard without building, publishing, rendering, scheduling, or exporting any external dashboard in this phase.

## Source references

This runbook builds on:

```text
docs/operations/p16-step-01.md
docs/operations/p15-readiness-report.md
docs/operations/p15-closeout-checklist.md
docs/operations/p15-step-04.md
docs/operations/p15-step-05.md
```

## Dashboard status

This phase is documentation-only.

The dashboard requirements do not create:

- a live external dashboard;
- a published public view;
- scheduled reporting;
- rendered screenshots;
- data exports;
- external package exports.

## Required dashboard sections

The operational dashboard requirements must cover:

- production health summary;
- CI health summary;
- workflow duration summary;
- queue health summary;
- worker success and failure summary;
- retry volume summary;
- database migration health summary;
- latency trend summary;
- storage growth summary;
- error-rate summary;
- alert volume and quality summary;
- service level review summary;
- support and incident trend summary;
- documentation freshness summary;
- action backlog summary.

## Operator views

Dashboard requirements must support these internal operator views:

- daily operator review;
- release readiness review;
- incident follow-up review;
- weekly operations review;
- monthly production health review;
- phase closeout review.

## Required dashboard fields

Each dashboard section must define:

- section identifier;
- section purpose;
- metric references;
- owner;
- reviewer;
- refresh expectation;
- evidence source;
- evidence sensitivity;
- review cadence;
- action route;
- stop condition;
- closure criteria.

## Display rules

Dashboard requirements may describe summarized display needs only.

Allowed display references:

- status label;
- trend direction;
- summarized count;
- summarized duration;
- summarized error rate;
- summarized queue depth;
- linked issue or PR reference;
- linked evidence archive entry.

Do not include:

- raw credentials;
- secret values;
- private runtime values;
- customer data exports;
- private environment dumps;
- external dashboard URLs created by this phase;
- rendered images;
- scheduled report outputs.

## Review cadence

Dashboard requirements should be reviewed:

- before release readiness review;
- after material incident;
- during weekly operations review;
- during monthly production health review;
- before phase closeout.

## Action routes

Dashboard requirement findings can route to:

- no action required;
- update metric catalog;
- update dashboard requirement;
- create implementation issue;
- update alert quality review;
- update service level review;
- update metrics evidence retention;
- update documentation freshness review;
- request more evidence;
- blocked by guardrail;
- rejected with reason.

## Ownership expectations

Required ownership:

- dashboard section owner;
- reviewer;
- evidence owner;
- action owner when action is required;
- validation owner when implementation is recommended;
- escalation owner for missing or misleading operator visibility.

Ownerless dashboard sections cannot close as reviewed.

## Stop conditions

Stop dashboard requirement closure if:

- dashboard section owner is missing;
- reviewer is missing;
- evidence source is missing;
- metric reference is missing;
- review cadence is missing;
- action owner is missing for required action;
- requirement asks for publishing;
- requirement asks for scheduling;
- requirement asks for rendering;
- requirement asks for external export;
- requirement includes secret values;
- requirement includes private runtime values;
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
tests/integration/test_p16_step_02.py
```

The validation checks source references, documentation-only status, dashboard sections, operator views, required fields, display rules, review cadence, action routes, ownership expectations, stop conditions, and guardrails.
