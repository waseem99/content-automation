# P16 Step 04

This step documents the internal service level review process for production observability and operating metrics.

Part of #222. Closes #226 after the PR merges.

## Goal

Create an internal, evidence-based review process for service-level targets, service-level risk, breach findings, owner assignment, follow-up routing, and closure criteria.

## Source references

This runbook builds on:

```text
docs/operations/p16-step-01.md
docs/operations/p16-step-02.md
docs/operations/p16-step-03.md
docs/operations/p15-step-03.md
docs/operations/p15-step-04.md
```

## Internal-only status

This process is internal and does not create:

- public service level commitments;
- public launch decisions;
- external status pages;
- published reports;
- scheduled reporting;
- rendered dashboards;
- exported evidence packages.

## Service-level target areas

Review internal targets for:

- CI completion health;
- workflow duration;
- queue processing health;
- worker completion health;
- retry containment;
- database migration health;
- API latency trend;
- error-rate trend;
- alert response quality;
- incident recurrence;
- storage growth review;
- documentation freshness.

## Required service-level fields

Each service-level review item must record:

- service-level identifier;
- target area;
- target description;
- measurement window;
- metric source;
- owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- target status;
- breach status;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Target statuses

Allowed target statuses:

- within target;
- watch;
- degraded;
- breached;
- insufficient evidence;
- blocked by guardrail.

## Breach review

A breach review must document:

- breach identifier;
- affected target;
- measurement window;
- observed signal;
- impact summary;
- source evidence;
- owner;
- reviewer;
- action owner;
- follow-up route;
- validation requirement;
- closure decision.

Breach findings require an owner, evidence, and follow-up route.

Critical or repeated breach findings require an action owner and validation requirement.

## Review cadence

Run service-level review:

- before release readiness review;
- after material incident;
- when repeated alerts indicate service-level risk;
- during weekly operations review;
- during monthly production health review;
- before phase closeout.

## Action routes

Allowed action routes:

- no action required;
- monitor next review;
- update metric catalog;
- update dashboard requirement;
- update alert quality review;
- update support and incident trend review;
- update documentation freshness review;
- create implementation issue;
- request more evidence;
- reject with reason;
- block by guardrail.

## Evidence rules

Allowed evidence includes:

- CI run identifiers;
- summarized metric trends;
- summarized incident notes;
- summarized alert quality notes;
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

## Ownership expectations

Required ownership:

- service-level owner;
- reviewer;
- evidence owner;
- breach owner when breached;
- action owner when action is required;
- validation owner when implementation is recommended;
- escalation owner for critical or repeated breach findings.

Ownerless service-level items cannot close as reviewed.

## Stop conditions

Stop service-level closure if:

- service-level owner is missing;
- reviewer is missing;
- metric source is missing;
- evidence source is missing;
- target status is missing;
- breach has no owner;
- breach has no evidence;
- breach has no follow-up route;
- critical or repeated breach has no action owner;
- validation requirement is missing for implementation;
- service-level evidence includes secret values;
- service-level evidence includes private runtime values;
- public launch decision is requested;
- workflow gate bypass is requested;
- automatic approval is requested;
- external export is requested.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No public production launch without explicit decision.
- No public service-level commitment from this phase.
- No breach closure without owner, evidence, and follow-up route.
- No critical or repeated breach closure without action owner.
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
tests/integration/test_p16_step_04.py
```

The validation checks source references, internal-only status, target areas, required fields, target statuses, breach review, cadence, action routes, evidence rules, ownership expectations, stop conditions, and guardrails.
