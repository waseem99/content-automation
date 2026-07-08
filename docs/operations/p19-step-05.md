# P19 Step 05

This step documents the security incident response playbook for production security readiness.

Part of #261. Closes #266 after the PR merges.

## Goal

Define security incident categories, severity, triage, escalation, containment, evidence handling, closure requirements, and post-incident follow-up routes.

## Source references

This security incident playbook builds on:

```text
docs/operations/p19-step-01.md
docs/operations/p19-step-02.md
docs/operations/p19-step-03.md
docs/operations/p19-step-04.md
docs/operations/p18-step-04.md
docs/operations/p17-step-05.md
docs/operations/p16-step-03.md
```

## Playbook status

This playbook is documentation-only.

It does not:

- create a live incident system;
- grant security access;
- execute containment actions;
- rotate secrets;
- delete production data;
- export incident evidence;
- approve production launch;
- schedule production launch;
- bypass workflow gates;
- replace named incident ownership.

## Security incident categories

Security incidents must be classified as one or more of:

- suspected secret exposure;
- confirmed secret exposure;
- unauthorized access concern;
- permission misuse concern;
- dependency vulnerability concern;
- supply-chain integrity concern;
- customer data exposure concern;
- private runtime value exposure;
- suspicious workflow activity;
- suspicious support evidence;
- suspicious incident evidence;
- restricted value found in logs;
- blocked by guardrail.

## Severity levels

Allowed severity levels:

- informational;
- low;
- medium;
- high;
- critical;
- blocked by guardrail.

Severity must consider exposure confidence, affected scope, customer impact, secret sensitivity, access impact, dependency impact, operational impact, and rollback relevance.

## Triage process

Security triage must follow this order:

1. record incident identifier;
2. classify incident category;
3. assign severity;
4. assign incident owner;
5. assign reviewer;
6. identify evidence owner;
7. record evidence source;
8. classify evidence sensitivity;
9. identify affected scope;
10. choose containment route;
11. choose escalation route;
12. define closure criteria;
13. create follow-up issue when implementation is required.

## Escalation rules

Escalate when:

- severity is high;
- severity is critical;
- secret exposure is confirmed;
- customer data exposure is suspected;
- private runtime value exposure is suspected;
- unauthorized access is suspected;
- dependency vulnerability is high or critical;
- workflow gate bypass is requested;
- incident owner is missing;
- evidence contains restricted values;
- containment owner is missing.

## Containment routes

Allowed containment routes:

- no containment required;
- redact and replace evidence;
- remove or replace restricted notes;
- route to secret rotation owner;
- route to access review owner;
- route to dependency review owner;
- route to support owner;
- create implementation issue;
- create security follow-up issue;
- block by guardrail.

Containment route documentation must not include live secret values or private runtime values.

## Evidence handling

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized incident notes;
- summarized triage notes;
- summarized containment notes;
- summarized escalation notes;
- summarized reviewer notes;
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
- raw incident dumps;
- screenshots containing restricted values;
- rendered incident materials;
- scheduled incident outputs.

## Required incident fields

Each security incident item must record:

- incident identifier;
- incident category;
- severity;
- affected scope;
- incident owner;
- reviewer;
- evidence owner;
- evidence source;
- evidence sensitivity;
- containment route;
- escalation route;
- action owner;
- validation requirement;
- closure criteria;
- post-incident follow-up route.

## Closure requirements

A security incident can close only when:

- incident owner is recorded;
- reviewer is recorded;
- evidence owner is recorded;
- severity is recorded;
- evidence source is recorded;
- evidence sensitivity is recorded;
- containment route is recorded;
- escalation route is recorded when required;
- restricted evidence is removed, redacted, or replaced;
- follow-up issue exists when implementation is required;
- closure criteria are met.

## Post-incident follow-up

Post-incident follow-up must decide whether to:

- update secrets and configuration hardening;
- update access control review;
- update data handling review;
- update dependency review;
- update support playbook;
- create implementation issue;
- create documentation issue;
- schedule owner review placeholder;
- block by guardrail;
- reject with reason.

## Stop conditions

Stop incident closure if:

- incident owner is missing;
- reviewer is missing;
- evidence owner is missing;
- severity is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- containment route is missing;
- required escalation route is missing;
- action owner is missing for required action;
- restricted evidence remains unredacted;
- confirmed secret exposure has no follow-up route;
- suspected customer data exposure has no escalation route;
- private runtime value is present;
- customer data export is requested;
- external package export is requested;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic incident closure.
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
tests/integration/test_p19_step_05.py
```

The validation checks source references, documentation-only status, incident categories, severity levels, triage process, escalation rules, containment routes, evidence handling, required fields, closure requirements, post-incident follow-up, stop conditions, and guardrails.
