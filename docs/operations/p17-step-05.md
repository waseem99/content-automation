# P17 Step 05

This step documents the post-release observation plan for controlled production launch readiness.

Part of #235. Closes #240 after the PR merges.

## Goal

Define the first-hour, first-24-hour, and first-7-day observation process for a controlled production release while preserving evidence safety, owner accountability, and incident response routes.

## Source references

This runbook builds on:

```text
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p17-step-03.md
docs/operations/p17-step-04.md
docs/operations/p16-step-01.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
```

## Observation plan status

This plan is observation-only.

It does not:

- approve a production launch;
- schedule a production launch;
- execute a production release;
- replace go/no-go approval;
- bypass workflow gates;
- export customer data;
- store secret values;
- store private runtime values;
- publish status pages;
- render launch materials.

## Required observation windows

The observation plan must include:

- first-hour observation window;
- first-24-hour observation window;
- first-7-day observation window;
- release owner handoff;
- operations owner handoff;
- support owner handoff;
- monitoring owner handoff;
- incident owner handoff;
- rollback owner handoff;
- evidence owner handoff;
- escalation owner handoff;
- closeout review window.

## Required observation fields

Each observation item must record:

- observation item identifier;
- observation window;
- metric or signal;
- watch criteria;
- expected state;
- observed state summary;
- evidence source;
- evidence sensitivity;
- owner;
- reviewer;
- status;
- incident route;
- escalation route;
- rollback route;
- action owner;
- validation requirement;
- closure criteria.

## Observation statuses

Allowed statuses:

- not started;
- normal;
- watch;
- degraded;
- incident triggered;
- rollback candidate;
- blocked;
- needs owner;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## First-hour watch criteria

The first-hour window must watch:

- exact release confirmation;
- CI baseline reference;
- service availability signal;
- API latency trend;
- error-rate trend;
- queue health trend;
- worker success and failure trend;
- database migration health;
- alert volume and quality;
- support signal volume;
- incident channel readiness;
- rollback trigger readiness.

## First-24-hour watch criteria

The first-24-hour window must watch:

- service stability trend;
- error recurrence trend;
- latency recurrence trend;
- queue backlog trend;
- worker retry trend;
- storage growth trend;
- alert noise trend;
- support ticket trend;
- incident recurrence trend;
- documentation correction needs;
- follow-up action owner assignment.

## First-7-day watch criteria

The first-7-day window must watch:

- service-level risk trend;
- repeated incident pattern;
- repeated alert pattern;
- operational workload trend;
- documentation freshness trend;
- metrics evidence retention quality;
- rollback readiness still-valid check;
- improvement backlog candidates;
- final post-release review readiness.

## Incident routes

Incident route must define:

- incident identifier;
- incident owner;
- severity level;
- affected signal;
- evidence source;
- escalation owner;
- rollback decision owner;
- support communication owner;
- action owner;
- follow-up route;
- closure criteria.

Incident evidence must not include restricted runtime values.

## Escalation rules

Escalate when:

- critical alert repeats;
- service-level risk is breached;
- rollback trigger is met;
- support volume spikes materially;
- error-rate trend is degraded;
- latency trend is degraded;
- queue backlog is sustained;
- incident owner is missing;
- evidence source is missing;
- restricted value appears in evidence.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized observation notes;
- summarized metric trend notes;
- summarized incident notes;
- summarized support notes;
- summarized rollback notes;
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
- rendered launch materials;
- scheduled release outputs.

## Stop conditions

Stop observation closure if:

- observation owner is missing;
- reviewer is missing;
- evidence source is missing;
- first-hour window is missing;
- first-24-hour window is missing;
- first-7-day window is missing;
- incident route is missing;
- escalation route is missing;
- rollback route is missing;
- incident owner is missing for an incident;
- action owner is missing for required action;
- rollback trigger has no decision owner;
- evidence contains secret values;
- evidence contains private runtime values;
- evidence contains customer data exports;
- evidence contains external package exports;
- external export is requested;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
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
tests/integration/test_p17_step_05.py
```

The validation checks source references, observation-only status, observation windows, fields, statuses, first-hour watch criteria, first-24-hour watch criteria, first-7-day watch criteria, incident routes, escalation rules, evidence rules, stop conditions, and guardrails.
