# P18 Step 04

This step documents the support playbook for production handover and operator enablement.

Part of #248. Closes #252 after the PR merges.

## Goal

Define common support cases, triage categories, severity levels, escalation rules, evidence handling, owner responsibilities, operator actions, and stop conditions for production support readiness.

## Source references

This playbook builds on:

```text
docs/operations/p18-step-01.md
docs/operations/p18-step-02.md
docs/operations/p18-step-03.md
docs/operations/p17-step-05.md
docs/operations/p17-readiness-report.md
docs/operations/p16-step-01.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
docs/operations/p16-readiness-report.md
```

## Playbook status

This support playbook is documentation-only.

It does not:

- create a live support queue;
- grant support access;
- approve production launch;
- schedule production launch;
- execute support automation;
- send customer communication;
- publish support material;
- render support material;
- export support evidence;
- bypass workflow gates.

## Support case categories

Support cases must be classified into one of these categories:

- access or permission issue;
- workflow or CI issue;
- release readiness question;
- observability or metric question;
- alert or incident signal;
- documentation gap;
- operator handover question;
- customer-impact concern;
- evidence handling concern;
- recurring support pattern;
- blocked by guardrail.

## Severity levels

Allowed severity levels:

- informational;
- low;
- medium;
- high;
- critical;
- blocked by guardrail.

Severity must consider customer impact, release impact, operational impact, evidence sensitivity, incident recurrence, and rollback relevance.

## Triage fields

Each support case must record:

- support case identifier;
- category;
- severity;
- summary;
- reported by;
- support owner;
- operator owner;
- incident owner when applicable;
- release owner when applicable;
- evidence source;
- evidence sensitivity;
- customer impact status;
- action route;
- action owner;
- escalation route;
- closure criteria.

## Common support cases

The playbook covers:

- failed exact-head CI;
- workflow cannot start;
- missing issue owner;
- missing PR reviewer;
- unclear issue scope;
- expanded PR scope;
- release approval question;
- blackout window conflict;
- alert noise question;
- repeated incident signal;
- support volume spike;
- rollback trigger question;
- documentation freshness gap;
- evidence sensitivity concern;
- restricted value found in notes.

## Triage process

Support triage must follow this order:

1. classify support case category;
2. assign severity;
3. assign support owner;
4. identify operator owner;
5. identify incident owner when applicable;
6. identify release owner when applicable;
7. capture evidence source;
8. classify evidence sensitivity;
9. determine customer impact status;
10. choose action route;
11. define closure criteria;
12. escalate if a stop condition is met.

## Escalation rules

Escalate when:

- severity is high;
- severity is critical;
- incident signal appears;
- repeated incident pattern appears;
- customer impact is suspected;
- rollback trigger is suggested;
- release decision is requested;
- support owner is missing;
- action owner is missing;
- evidence source is missing;
- evidence sensitivity is unclear;
- restricted value appears in evidence;
- workflow gate bypass is requested.

## Operator actions

Operators may:

- gather summarized support context;
- link issue or PR references;
- capture CI run identifiers;
- route case to support owner;
- route incident signal to incident owner;
- route release question to release owner;
- request evidence replacement;
- document closure notes.

Operators must not:

- export customer data;
- store secret values;
- store private runtime values;
- publish support evidence;
- send customer communication without owner approval;
- close high or critical cases without owner review;
- bypass workflow gates.

## Evidence handling

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized support notes;
- summarized operator notes;
- summarized incident notes;
- summarized alert notes;
- summarized customer-impact notes;
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
- rendered support materials;
- scheduled support outputs.

## Closure requirements

A support case can close only when:

- category is recorded;
- severity is recorded;
- support owner is recorded;
- action owner is recorded when action is required;
- evidence source is recorded;
- evidence sensitivity is recorded;
- escalation route is recorded when required;
- closure criteria are met;
- restricted evidence is removed or replaced;
- follow-up issue is created when implementation is required.

## Stop conditions

Stop support closure if:

- support owner is missing;
- action owner is missing for required action;
- evidence source is missing;
- evidence sensitivity is missing;
- severity is high or critical without escalation;
- customer impact is suspected without owner review;
- incident signal has no incident owner;
- rollback trigger has no release owner;
- release decision is implied;
- production launch is implied;
- workflow gate bypass is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- customer data export is requested;
- external export is requested.

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
tests/integration/test_p18_step_04.py
```

The validation checks source references, documentation-only status, support case categories, severity levels, triage fields, common support cases, triage process, escalation rules, operator actions, evidence handling, closure requirements, stop conditions, and guardrails.
