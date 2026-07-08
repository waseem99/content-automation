# P16 Step 05

This step documents metrics evidence retention expectations for production observability and operating metrics.

Part of #222. Closes #227 after the PR merges.

## Goal

Define what metrics evidence may be retained as references or summaries, what must be excluded, who owns retention decisions, and how retention is reviewed without exposing restricted values or exporting private material.

## Source references

This runbook builds on:

```text
docs/operations/p16-step-01.md
docs/operations/p16-step-02.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p15-step-05.md
docs/operations/p15-readiness-report.md
```

## Evidence retention scope

Metrics evidence retention covers:

- CI run evidence;
- workflow duration evidence;
- queue health evidence;
- worker success and failure evidence;
- retry volume evidence;
- database migration health evidence;
- latency trend evidence;
- storage growth evidence;
- error-rate evidence;
- alert quality evidence;
- service-level review evidence;
- support and incident trend evidence;
- documentation freshness evidence;
- phase closeout evidence.

## Retained evidence types

Allowed retained evidence types:

- CI run identifier;
- summarized metric trend;
- summarized workflow duration note;
- summarized queue health note;
- summarized incident note;
- summarized alert quality note;
- summarized service-level note;
- issue or PR reference;
- merge commit reference;
- evidence archive entry name;
- owner review note.

## Excluded evidence types

Do not retain:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- raw logs with restricted values;
- rendered dashboards;
- scheduled report outputs;
- public status pages created by this phase.

## Required retention fields

Each retained evidence item must record:

- evidence identifier;
- metric reference;
- evidence type;
- source reference;
- owner;
- reviewer;
- sensitivity classification;
- retention decision;
- retention reference;
- review cadence;
- action route;
- validation requirement;
- closure criteria.

## Sensitivity classifications

Allowed sensitivity classifications:

- public reference;
- internal summary;
- restricted summary;
- blocked restricted value;
- customer data risk;
- secret value risk;
- private runtime risk;
- external export risk.

## Retention decisions

Allowed retention decisions:

- retain reference;
- retain summary;
- rotate summary;
- archive reference;
- needs owner;
- needs reviewer;
- needs evidence;
- remove restricted value;
- reject with reason;
- block by guardrail.

## Review cadence

Review metrics evidence retention:

- before phase closeout;
- during monthly production health review;
- after material incident;
- after service-level review updates;
- after alert quality review updates;
- after documentation freshness review updates;
- when metric evidence changes.

## Action routes

Allowed action routes:

- no action required;
- update retained summary;
- update evidence owner;
- update evidence reference;
- update sensitivity classification;
- update metric catalog;
- update documentation freshness review;
- create implementation issue;
- request more evidence;
- reject with reason;
- block by guardrail.

## Ownership expectations

Required ownership:

- evidence owner;
- reviewer;
- metric owner;
- retention owner;
- action owner when action is required;
- validation owner when implementation is recommended;
- escalation owner for restricted value risk or external export risk.

Ownerless retained evidence cannot close as reviewed.

## Stop conditions

Stop evidence retention closure if:

- evidence owner is missing;
- reviewer is missing;
- metric reference is missing;
- source reference is missing;
- sensitivity classification is missing;
- retention decision is missing;
- retention reference is missing;
- action owner is missing for required action;
- validation requirement is missing for implementation;
- evidence contains secret values;
- evidence contains private runtime values;
- evidence contains customer data exports;
- evidence contains external package exports;
- evidence requires publishing;
- evidence requires scheduling;
- evidence requires rendering;
- evidence requires external export;
- workflow gate bypass is requested;
- automatic approval is requested.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No retained secret values.
- No retained private runtime values.
- No customer data exports.
- No external package exports.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p16_step_05.py
```

The validation checks source references, retention scope, retained evidence types, excluded evidence types, required retention fields, sensitivity classifications, retention decisions, review cadence, action routes, ownership expectations, stop conditions, and guardrails.
