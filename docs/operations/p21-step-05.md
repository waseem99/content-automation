# P21 Step 05

This step documents the escalation drill and contact routing plan for production operational drill and recovery readiness.

Part of #287. Closes #292 after the PR merges.

## Goal

Define documentation-only escalation drill and contact routing so operators can choose the right owner, route, evidence class, and follow-up path without sending real notifications or external communication.

## Source references

This escalation drill builds on:

```text
docs/operations/p21-step-01.md
docs/operations/p21-step-02.md
docs/operations/p21-step-04.md
docs/operations/p20-step-03.md
docs/operations/p19-step-05.md
docs/operations/p18-step-02.md
docs/operations/p18-step-04.md
```

## Drill status

This escalation drill and contact routing plan is documentation-only.

It does not:

- notify external contacts;
- send customer communication;
- schedule meetings;
- schedule drill automation;
- execute live escalation;
- approve production launch;
- bypass workflow gates;
- publish routing evidence;
- render routing evidence;
- export restricted evidence.

## Escalation roles

Required roles:

- facilitator;
- operator owner;
- support owner;
- incident owner;
- release owner;
- evidence owner;
- documentation owner;
- reviewer;
- observer.

## Routing matrix

| Scenario | Primary route | Secondary route | Guardrail |
| --- | --- | --- | --- |
| exact-head CI failure | operator owner | reviewer | no merge without exact-head CI |
| workflow cannot start | operator owner | documentation owner | no workflow gate bypass |
| support case suggests customer impact | support owner | incident owner | no customer data export |
| security incident signal | incident owner | evidence owner | no secret values in evidence |
| restricted evidence suspected | evidence owner | incident owner | restricted value must be redacted or replaced |
| rollback decision question | release owner | incident owner | no rollback without explicit approval |
| restore decision question | release owner | incident owner | no restore without explicit approval |
| blackout window conflict | release owner | reviewer | no release during blackout window |
| missing owner | documentation owner | operator owner | no closeout without owner |
| workflow gate bypass request | reviewer | release owner | block by guardrail |

## Drill prompts

Facilitator prompts must ask:

- Which scenario is being exercised?
- Which primary route applies?
- Which secondary route applies?
- Which role owns the response?
- Which evidence is safe to retain?
- Which evidence sensitivity applies?
- Is any restricted value suspected?
- Is customer impact suspected?
- Is rollback or restore explicitly approved?
- What would block closure?

## Contact placeholders

Contact routing must use placeholders only:

- role placeholder;
- team placeholder;
- contact route placeholder;
- response window placeholder;
- backup owner placeholder;
- escalation note placeholder.

Do not record real phone numbers, private email addresses, chat handles, customer identifiers, or external contact details.

## Response expectations

Each drill participant must demonstrate that they can:

- select the correct primary route;
- select the correct secondary route when required;
- identify the response owner;
- identify the reviewer;
- classify evidence sensitivity;
- avoid restricted evidence capture;
- avoid external notification;
- avoid implied live escalation;
- record a follow-up route;
- identify stop conditions.

## Evidence fields

Each escalation drill record must include:

- escalation drill identifier;
- scenario name;
- primary route;
- secondary route;
- role placeholder;
- contact route placeholder;
- response window placeholder;
- evidence source;
- evidence sensitivity;
- expected response summary;
- actual response summary;
- escalation result;
- follow-up route;
- reviewer notes;
- closure criteria.

## Escalation results

Allowed results:

- pass;
- pass with notes;
- partial pass;
- fail;
- blocked;
- follow-up required;
- blocked by guardrail.

## Follow-up routes

Allowed follow-up routes:

- no follow-up required;
- update recovery drill plan;
- update tabletop exercise;
- update operator failure-mode checklist;
- update support playbook;
- update security incident playbook;
- update audit trail evidence;
- create implementation issue;
- create documentation issue;
- block by guardrail.

## Evidence rules

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized routing note;
- summarized drill note;
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
- real phone numbers;
- private email addresses;
- customer identifiers;
- rendered routing materials;
- scheduled routing outputs.

## Stop conditions

Stop escalation drill closure if:

- escalation drill identifier is missing;
- scenario name is missing;
- primary route is missing;
- role placeholder is missing;
- contact route placeholder is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- escalation result is missing;
- reviewer is missing;
- real external contact is recorded;
- external notification is implied;
- live escalation is implied;
- rollback is implied without explicit approval;
- restore is implied without explicit approval;
- secret value is present;
- private runtime value is present;
- customer data export is requested;
- external export is requested;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic escalation.
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
tests/integration/test_p21_step_05.py
```

The validation checks source references, documentation-only status, escalation roles, routing matrix, drill prompts, contact placeholders, response expectations, evidence fields, results, follow-up routes, evidence rules, stop conditions, and guardrails.
