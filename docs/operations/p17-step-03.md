# P17 Step 03

This step documents the production release dry-run and rehearsal process.

Part of #235. Closes #238 after the PR merges.

## Goal

Define a safe release rehearsal process that validates the production release path without executing, scheduling, publishing, rendering, exporting, or launching production.

## Source references

This runbook builds on:

```text
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p16-step-01.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
```

## Rehearsal status

This process is simulation-only.

It does not:

- execute a production release;
- schedule a production release;
- approve a production release;
- publish release notes;
- render launch materials;
- export release packages;
- change production configuration;
- run live rollback actions;
- bypass workflow gates.

## Required rehearsal sections

The dry-run process must include:

- rehearsal identifier;
- rehearsal scope;
- release candidate reference;
- participant list;
- rehearsal owner;
- simulated release steps;
- simulated migration steps;
- simulated rollback steps;
- monitoring rehearsal steps;
- alert routing rehearsal steps;
- communication rehearsal steps;
- failure handling steps;
- stop condition review;
- evidence capture summary;
- rehearsal decision summary.

## Required rehearsal fields

Each rehearsal item must record:

- rehearsal item identifier;
- rehearsal area;
- simulated step;
- expected result;
- actual result summary;
- evidence source;
- evidence sensitivity;
- owner;
- reviewer;
- status;
- failure mode;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Rehearsal statuses

Allowed statuses:

- not started;
- simulated successfully;
- simulated with notes;
- failed rehearsal;
- blocked;
- needs owner;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## Simulated release steps

Rehearsal must simulate:

- release candidate verification;
- exact-head CI evidence review;
- release checklist review;
- environment readiness review;
- configuration readiness review;
- migration readiness review;
- rollback readiness review;
- monitoring readiness review;
- go/no-go handoff review;
- post-release observation handoff.

## Failure handling

Failure handling must define:

- failure identifier;
- failure area;
- observed failure summary;
- owner;
- reviewer;
- evidence source;
- action route;
- action owner;
- retry decision;
- rollback rehearsal decision;
- validation requirement;
- closure criteria.

Rehearsal failures must not be ignored or converted into approval without owner and evidence.

## Rollback rehearsal

Rollback rehearsal must confirm:

- rollback owner;
- rollback trigger;
- rollback route;
- rollback communication route;
- rollback validation route;
- rollback evidence source;
- rollback stop condition.

Rollback rehearsal cannot execute live rollback actions.

## Communication rehearsal

Communication rehearsal must confirm:

- release decision owner;
- release communication owner;
- rollback communication owner;
- incident communication owner;
- support communication route;
- internal update route;
- go/no-go meeting reference.

Communication rehearsal cannot send or schedule public communications.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized rehearsal notes;
- summarized failure notes;
- summarized rollback notes;
- summarized monitoring notes;
- summarized communication notes;
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

Stop rehearsal closure if:

- rehearsal owner is missing;
- reviewer is missing;
- release candidate reference is missing;
- simulated release steps are missing;
- rollback rehearsal is missing;
- monitoring rehearsal is missing;
- failure handling is missing;
- communication rehearsal is missing;
- unresolved rehearsal failure has no action owner;
- evidence source is missing;
- rehearsal implies live launch;
- rehearsal schedules a production release;
- rehearsal sends public communication;
- workflow gate bypass is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- external export is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No public production launch without explicit decision.
- No live production launch during rehearsal.
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
tests/integration/test_p17_step_03.py
```

The validation checks source references, simulation-only status, rehearsal sections, fields, statuses, simulated release steps, failure handling, rollback rehearsal, communication rehearsal, evidence rules, stop conditions, and guardrails.
