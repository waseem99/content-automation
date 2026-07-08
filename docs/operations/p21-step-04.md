# P21 Step 04

This step documents the operator failure-mode checklist for production operational drill and recovery readiness.

Part of #287. Closes #291 after the PR merges.

## Goal

Define common operator failure modes, detection signals, safe response routes, evidence capture, escalation paths, and stop conditions without triggering live operational changes.

## Source references

This checklist builds on:

```text
docs/operations/p21-step-01.md
docs/operations/p21-step-02.md
docs/operations/p21-step-03.md
docs/operations/p20-step-03.md
docs/operations/p18-step-01.md
docs/operations/p18-step-04.md
docs/operations/p16-step-01.md
docs/operations/p16-readiness-report.md
```

## Checklist status

This operator failure-mode checklist is documentation-only.

It does not:

- execute live operator actions;
- change production configuration;
- approve production launch;
- schedule operational work;
- notify external contacts;
- bypass workflow gates;
- merge changes;
- publish checklist evidence;
- render checklist evidence;
- export restricted evidence.

## Failure modes

The checklist must cover:

- exact-head CI failure;
- workflow cannot start;
- issue owner missing;
- reviewer missing;
- evidence source missing;
- evidence sensitivity missing;
- support case without owner;
- incident signal without owner;
- rollback decision without approval;
- restore decision without approval;
- blackout conflict;
- workflow gate bypass request.

## Detection signals

Detection signals include:

- failed CI run;
- missing run identifier;
- open PR without owner;
- open issue without next action;
- support note requiring escalation;
- incident note requiring escalation;
- restricted value suspected;
- customer impact suspected;
- release decision requested;
- stale runbook detected.

## Safe response routes

Allowed response routes:

- no action required;
- request missing owner;
- request reviewer;
- request evidence source;
- request evidence sensitivity;
- create implementation issue;
- create documentation issue;
- escalate to support owner;
- escalate to incident owner;
- escalate to release owner;
- escalate to evidence owner;
- block by guardrail.

## Evidence fields

Each failure-mode checklist item must record:

- checklist item identifier;
- failure mode;
- detection signal;
- operator owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- safe response route;
- escalation route;
- action owner;
- validation requirement;
- closure criteria;
- pass/fail status.

## Pass/fail statuses

Allowed statuses:

- pass;
- pass with notes;
- fail;
- blocked;
- needs owner;
- needs reviewer;
- needs evidence;
- needs escalation;
- blocked by guardrail.

## Evidence rules

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized operator note;
- summarized support note;
- summarized incident note;
- summarized reviewer note;
- evidence archive entry name.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- customer data exports;
- external package exports;
- raw logs with restricted values;
- screenshots containing restricted values;
- rendered checklist materials;
- scheduled checklist outputs.

## Stop conditions

Stop checklist closure if:

- checklist item identifier is missing;
- failure mode is missing;
- detection signal is missing;
- operator owner is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- safe response route is missing;
- pass/fail status is missing;
- escalation route is missing for high-risk item;
- live operator action is implied;
- production change is implied;
- external notification is implied;
- secret value is present;
- private runtime value is present;
- customer data export is requested;
- external export is requested;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic operator action.
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
tests/integration/test_p21_step_04.py
```

The validation checks source references, documentation-only status, failure modes, detection signals, safe response routes, evidence fields, statuses, evidence rules, stop conditions, and guardrails.
