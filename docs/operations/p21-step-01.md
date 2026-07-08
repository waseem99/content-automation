# P21 Step 01

This step documents the recovery drill plan for production operational drill and recovery readiness.

Part of #287. Closes #288 after the PR merges.

## Goal

Define a documentation-only recovery drill that proves operators know how to identify a recovery scenario, capture evidence, escalate safely, and determine pass/fail outcomes without executing live recovery actions.

## Source references

This drill plan builds on:

```text
docs/operations/p20-readiness-report.md
docs/operations/p20-step-03.md
docs/operations/p19-step-05.md
docs/operations/p18-step-01.md
docs/operations/p18-step-04.md
docs/operations/p17-readiness-report.md
docs/operations/p17-step-05.md
docs/operations/p16-readiness-report.md
```

## Drill status

This recovery drill plan is documentation-only.

It does not:

- execute live recovery;
- execute live rollback;
- restore production data;
- change production configuration;
- notify external contacts;
- schedule drill automation;
- approve production launch;
- bypass workflow gates;
- publish drill evidence;
- export restricted evidence.

## Drill assumptions

The drill assumes:

- all actions are simulated;
- evidence is summary-only;
- no customer data is copied;
- no private runtime values are recorded;
- no secret values are recorded;
- no production systems are changed;
- all follow-up work uses scoped issues and PRs;
- required validation uses exact-head CI.

## Drill roles

Required roles:

- drill facilitator;
- operator owner;
- support owner;
- incident owner;
- release owner;
- evidence owner;
- reviewer;
- observer.

## Trigger scenarios

The recovery drill must cover:

- failed exact-head CI during release preparation;
- operator detects missing owner;
- support case suggests customer impact;
- security incident suggests restricted evidence exposure;
- rollback decision question appears;
- restore decision question appears;
- evidence source is incomplete;
- escalation route is missing;
- blackout window conflict appears;
- workflow gate bypass is requested.

## Drill evidence fields

Each drill record must include:

- drill record identifier;
- scenario name;
- simulated trigger;
- drill role owner;
- facilitator;
- reviewer;
- evidence source;
- evidence sensitivity;
- expected response route;
- actual response summary;
- escalation route;
- action owner;
- pass/fail result;
- follow-up route;
- closure criteria.

## Pass criteria

A drill passes when:

- scenario is classified;
- owner is identified;
- reviewer is identified;
- evidence source is recorded;
- evidence sensitivity is recorded;
- escalation route is selected when required;
- restricted values are not recorded;
- no live recovery action is taken;
- follow-up issue is proposed when implementation is needed;
- pass/fail result is recorded.

## Fail criteria

A drill fails when:

- owner is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- restricted value is copied;
- live recovery action is implied;
- live rollback is implied;
- production change is implied;
- external notification is implied;
- workflow gate bypass is requested;
- escalation is skipped for high-risk scenario.

## Evidence rules

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized drill note;
- summarized response note;
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
- rendered drill materials;
- scheduled drill outputs.

## Stop conditions

Stop drill closeout if:

- drill record identifier is missing;
- scenario name is missing;
- role owner is missing;
- facilitator is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- pass/fail result is missing;
- escalation route is missing for high-risk scenario;
- live recovery is implied;
- live rollback is implied;
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
tests/integration/test_p21_step_01.py
```

The validation checks source references, documentation-only status, assumptions, roles, trigger scenarios, evidence fields, pass/fail criteria, evidence rules, stop conditions, guardrails, and P21 CI wildcard coverage.
