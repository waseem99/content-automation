# P20 Step 02

This step documents the security control evidence index for production audit readiness.

Part of #274. Closes #276 after the PR merges.

## Goal

Create an audit-ready index for security-control evidence that remains summary-only, owner-reviewed, exact-head-CI traceable, and free of secret values, private runtime values, customer data exports, and restricted evidence.

## Source references

This index builds on:

```text
docs/operations/p20-step-01.md
docs/operations/p19-step-01.md
docs/operations/p19-step-02.md
docs/operations/p19-step-04.md
docs/operations/p19-step-05.md
docs/operations/p19-readiness-report.md
docs/operations/p18-step-02.md
docs/operations/p18-step-05.md
```

## Index status

This security control evidence index is documentation-only.

It does not:

- grant security access;
- rotate secrets;
- change configuration;
- update dependencies;
- execute incident containment;
- approve production launch;
- schedule production launch;
- publish control evidence;
- render control evidence;
- export restricted evidence;
- bypass workflow gates.

## Security control categories

The index must cover security evidence for:

- secrets and configuration hardening;
- access control and permission review;
- data handling and privacy controls;
- dependency and supply-chain review;
- security incident response;
- evidence handling and retention;
- release gate and exact-head CI controls;
- manual approval controls;
- owner and reviewer controls;
- exception and stop-condition controls.

## Evidence mapping

Each security control must map to:

- source runbook;
- source issue or PR;
- source merge commit when applicable;
- source CI run identifier when applicable;
- control owner;
- reviewer;
- evidence class;
- evidence sensitivity;
- review cadence;
- escalation route;
- closure criteria.

## Evidence classes

Allowed evidence classes:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized security review note;
- summarized control owner note;
- summarized reviewer note;
- summarized access review note;
- summarized incident review note;
- summarized dependency review note;
- evidence archive entry name.

Forbidden evidence classes:

- secret value;
- private runtime value;
- raw credential;
- production token;
- private environment dump;
- customer data export;
- external package export;
- raw dependency archive;
- raw incident dump;
- raw log with restricted value;
- screenshot containing restricted value.

## Required evidence fields

Each security control evidence item must record:

- security evidence identifier;
- security control category;
- control objective;
- source document;
- source issue or PR;
- control owner;
- reviewer;
- evidence class;
- evidence sensitivity;
- review cadence;
- control status;
- exception status;
- escalation route;
- action owner;
- validation requirement;
- closure criteria.

## Control statuses

Allowed control statuses:

- not started;
- indexed;
- reviewed;
- reviewed with notes;
- needs owner;
- needs reviewer;
- needs evidence;
- needs escalation;
- blocked;
- blocked by guardrail;
- rejected with reason.

## Exception handling

Security control exceptions must record:

- exception identifier;
- exception owner;
- business reason summary;
- approver;
- reviewer;
- expiry or review point;
- compensating control;
- evidence source;
- escalation route;
- closure criteria.

Exceptions cannot be permanent and cannot approve restricted evidence retention.

## Review cadence

Review cadence options:

- per PR closeout;
- before compliance closeout;
- after security incident;
- after access change;
- after dependency change;
- after configuration change;
- after guardrail change;
- monthly during steady operation.

## Escalation routes

Escalate security control evidence when:

- control owner is missing;
- reviewer is missing;
- evidence sensitivity is unclear;
- exception lacks expiry;
- high or critical issue is referenced;
- secret exposure is suspected;
- unauthorized access is suspected;
- dependency vulnerability is high or critical;
- workflow gate bypass is requested;
- production launch is implied.

## Stop conditions

Stop security control index closure if:

- security evidence identifier is missing;
- security control category is missing;
- control objective is missing;
- source document is missing;
- source issue or PR is missing;
- control owner is missing;
- reviewer is missing;
- evidence class is missing;
- evidence sensitivity is missing;
- review cadence is missing;
- exception is permanent;
- exception lacks expiry or review point;
- secret value is present;
- private runtime value is present;
- raw credential is present;
- production token is present;
- customer data export is requested;
- external package export is requested;
- production launch is implied;
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
tests/integration/test_p20_step_02.py
```

The validation checks source references, documentation-only status, security control categories, evidence mapping, evidence classes, required fields, control statuses, exception handling, review cadence, escalation routes, stop conditions, and guardrails.
