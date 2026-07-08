# P17 Step 02

This step documents the production release checklist for controlled launch readiness.

Part of #235. Closes #237 after the PR merges.

## Goal

Create a production release checklist that verifies readiness inputs while preserving manual approval, release calendar requirements, blackout checks, rollback readiness, and evidence safety.

## Source references

This runbook builds on:

```text
docs/operations/p17-step-01.md
docs/operations/p16-readiness-report.md
docs/operations/p16-step-01.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
```

## Checklist status

This checklist is documentation-only.

It does not:

- approve a production launch;
- schedule a production launch;
- execute a production release;
- publish release notes;
- render launch materials;
- export release packages;
- bypass workflow gates;
- replace explicit human confirmation.

## Required checklist sections

The production release checklist must include:

- release candidate check;
- environment readiness check;
- configuration readiness check;
- secrets handling check;
- migration readiness check;
- rollback readiness check;
- monitoring readiness check;
- alert readiness check;
- support readiness check;
- documentation readiness check;
- calendar entry check;
- blackout window check;
- communication readiness check;
- evidence retention check;
- final manual confirmation check.

## Required checklist fields

Each checklist item must record:

- checklist item identifier;
- checklist section;
- check description;
- expected evidence;
- evidence source;
- evidence sensitivity;
- owner;
- reviewer;
- status;
- blocker status;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Checklist statuses

Allowed statuses:

- not started;
- ready;
- ready with notes;
- blocked;
- not applicable with reason;
- needs owner;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## Environment readiness

Environment readiness must confirm:

- target environment is named;
- release candidate is identified;
- required configuration is reviewed;
- secrets handling is reviewed without recording secret values;
- migration path is reviewed;
- rollback route is identified;
- monitoring signals are defined;
- release owners are named;
- release calendar entry is present;
- blackout window is checked.

## Rollback readiness

Rollback readiness must define:

- rollback owner;
- rollback trigger;
- rollback route;
- rollback evidence source;
- rollback communication owner;
- rollback validation requirement;
- rollback closure criteria.

Release cannot be marked ready without rollback readiness.

## Monitoring readiness

Monitoring readiness must define:

- health signal list;
- alert routing owner;
- service-level watch criteria;
- post-release observation owner;
- incident route;
- evidence retention route.

Release cannot be marked ready without monitoring readiness.

## Calendar and blackout rules

Release readiness requires:

- release calendar entry;
- release window owner;
- blackout window check;
- communication owner;
- decision owner;
- go/no-go record reference.

No release may proceed during a blackout window.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized readiness notes;
- summarized configuration review notes;
- summarized migration review notes;
- summarized rollback notes;
- summarized monitoring notes;
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

Stop checklist closure if:

- owner is missing;
- reviewer is missing;
- evidence source is missing;
- release candidate is missing;
- target environment is missing;
- rollback readiness is missing;
- monitoring readiness is missing;
- calendar entry is missing;
- blackout check is missing;
- go/no-go record reference is missing;
- automatic release is implied;
- public launch is implied;
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
tests/integration/test_p17_step_02.py
```

The validation checks source references, documentation-only status, checklist sections, fields, statuses, environment readiness, rollback readiness, monitoring readiness, calendar and blackout rules, evidence rules, stop conditions, and guardrails.
