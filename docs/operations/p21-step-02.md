# P21 Step 02

This step documents the incident tabletop exercise for production operational drill and recovery readiness.

Part of #287. Closes #289 after the PR merges.

## Goal

Define a documentation-only tabletop exercise that tests whether operators can classify incidents, make safe decisions, escalate correctly, capture evidence, and route follow-up without triggering live incident actions.

## Source references

This tabletop exercise builds on:

```text
docs/operations/p21-step-01.md
docs/operations/p20-step-03.md
docs/operations/p20-readiness-report.md
docs/operations/p19-step-05.md
docs/operations/p18-step-04.md
docs/operations/p18-step-02.md
docs/operations/p16-step-03.md
```

## Exercise status

This tabletop exercise is documentation-only.

It does not:

- create a live incident;
- execute containment actions;
- rotate secrets;
- notify external contacts;
- send customer communication;
- schedule external meetings;
- approve production launch;
- bypass workflow gates;
- publish tabletop evidence;
- export restricted evidence.

## Participant roles

Required participants:

- facilitator;
- incident owner;
- operator owner;
- support owner;
- release owner;
- evidence owner;
- reviewer;
- observer.

## Tabletop scenarios

The tabletop must include:

- suspected secret exposure;
- confirmed restricted evidence in notes;
- support case suggests customer impact;
- high-severity dependency finding;
- workflow cannot start;
- exact-head CI fails;
- rollback decision question appears;
- missing incident owner;
- missing evidence sensitivity;
- workflow gate bypass is requested.

## Decision points

Each scenario must test decisions for:

- incident category;
- severity level;
- incident owner;
- evidence owner;
- evidence sensitivity;
- containment route;
- escalation route;
- customer-impact status;
- follow-up issue requirement;
- closure criteria.

## Exercise prompts

Facilitator prompts must ask:

- What is the incident category?
- What is the severity?
- Who owns the response?
- Which evidence is safe to retain?
- Which evidence must be redacted or replaced?
- Which escalation route applies?
- Is a rollback or restore decision actually approved?
- Is a follow-up issue required?
- What would block closure?

## Evidence capture fields

Each tabletop record must include:

- tabletop record identifier;
- scenario name;
- prompt set;
- participant roles;
- expected decision;
- actual decision summary;
- evidence source;
- evidence sensitivity;
- escalation route;
- follow-up route;
- scoring result;
- reviewer notes;
- closure criteria.

## Scoring

Allowed scoring results:

- pass;
- pass with notes;
- partial pass;
- fail;
- blocked;
- blocked by guardrail;
- follow-up required.

## Follow-up routes

Allowed follow-up routes:

- no follow-up required;
- update recovery drill plan;
- update security incident playbook;
- update support playbook;
- update audit trail evidence;
- create implementation issue;
- create documentation issue;
- escalate to incident owner;
- escalate to evidence owner;
- block by guardrail.

## Evidence rules

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized tabletop note;
- summarized decision note;
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
- rendered tabletop materials;
- scheduled tabletop outputs.

## Stop conditions

Stop tabletop closure if:

- scenario name is missing;
- facilitator is missing;
- incident owner is missing for incident scenario;
- evidence owner is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- scoring result is missing;
- escalation route is missing for high-risk scenario;
- live incident action is implied;
- external communication is implied;
- customer data export is requested;
- secret value is present;
- private runtime value is present;
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
tests/integration/test_p21_step_02.py
```

The validation checks source references, documentation-only status, participant roles, tabletop scenarios, decision points, prompts, evidence fields, scoring, follow-up routes, evidence rules, stop conditions, and guardrails.
