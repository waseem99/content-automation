# P17 Step 04

This step documents the manual Go / No-Go approval record for controlled production release readiness.

Part of #235. Closes #239 after the PR merges.

## Goal

Define a manual, explicit approval record that captures approvers, evidence, blocker disposition, risk acceptance, rollback readiness, monitoring readiness, and decision lock conditions before any production launch decision.

## Source references

This runbook builds on:

```text
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p17-step-03.md
docs/operations/p16-readiness-report.md
docs/operations/p16-step-03.md
docs/operations/p16-step-04.md
docs/operations/p16-step-05.md
```

## Approval record status

This approval record is manual-only.

It does not:

- approve a production launch by itself;
- schedule a production launch;
- execute a production release;
- grant automatic approval;
- replace named approvers;
- bypass workflow gates;
- ignore unresolved blockers;
- publish release notes;
- render launch materials;
- export release packages.

## Required approval sections

The Go / No-Go approval record must include:

- approval record identifier;
- release candidate reference;
- release decision owner;
- approver list;
- reviewer list;
- release checklist reference;
- dry-run rehearsal reference;
- exact-head CI evidence reference;
- rollback readiness reference;
- monitoring readiness reference;
- blackout check reference;
- calendar entry reference;
- unresolved blocker summary;
- risk acceptance summary;
- final go/no-go status;
- decision lock summary.

## Required approval fields

Each approval item must record:

- approval item identifier;
- approval area;
- required approver;
- reviewer;
- source evidence;
- evidence sensitivity;
- decision status;
- blocker status;
- risk status;
- rollback status;
- monitoring status;
- calendar status;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Decision statuses

Allowed decision statuses:

- go pending;
- go approved;
- no-go;
- deferred;
- blocked;
- needs approver;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

A go approved status requires explicit named approval and cannot be inferred from passing CI alone.

## Approver requirements

The approval record must identify:

- release decision owner;
- technical approver;
- operations approver;
- rollback approver;
- monitoring approver;
- support approver;
- communication approver;
- risk acceptance approver when risk is accepted.

Approver placeholders cannot close as approved.

## Blocker disposition

Every blocker must record:

- blocker identifier;
- blocker owner;
- blocker evidence;
- blocker impact summary;
- blocker decision;
- action owner;
- target follow-up route;
- closure criteria.

Unresolved blockers must result in no-go, deferred, or blocked status.

## Risk acceptance rules

Risk acceptance must document:

- risk identifier;
- risk owner;
- risk impact summary;
- acceptance reason;
- accepting approver;
- expiry or review point;
- rollback dependency;
- monitoring dependency;
- follow-up route.

Risk cannot be accepted without a named approver, evidence, and review point.

## Rollback readiness confirmation

Approval cannot close as go approved unless rollback readiness confirms:

- rollback owner;
- rollback trigger;
- rollback route;
- rollback communication owner;
- rollback validation requirement;
- rollback evidence source.

## Monitoring readiness confirmation

Approval cannot close as go approved unless monitoring readiness confirms:

- health signal list;
- alert routing owner;
- service-level watch criteria;
- post-release observation owner;
- incident route;
- evidence retention route.

## Decision lock conditions

Lock the approval decision if:

- required approver is missing;
- exact-head CI evidence is missing;
- release checklist is incomplete;
- dry-run rehearsal is incomplete;
- rollback readiness is missing;
- monitoring readiness is missing;
- blackout check is missing;
- calendar entry is missing;
- unresolved blocker has no disposition;
- risk acceptance is missing approver or review point;
- approval is automatic;
- workflow gate bypass is requested;
- release evidence contains restricted values.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized approval notes;
- summarized blocker notes;
- summarized risk notes;
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

Stop approval closure if:

- release decision owner is missing;
- required approver is missing;
- reviewer is missing;
- source evidence is missing;
- exact-head CI evidence is missing;
- release checklist reference is missing;
- dry-run rehearsal reference is missing;
- rollback readiness reference is missing;
- monitoring readiness reference is missing;
- blackout check reference is missing;
- calendar entry reference is missing;
- unresolved blocker has no disposition;
- risk acceptance has no named approver;
- risk acceptance has no review point;
- approval is automatic;
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
- No launch from approval record alone.
- No release without calendar entry.
- No release during blackout window.
- No unresolved blocker closure as go approved.
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
tests/integration/test_p17_step_04.py
```

The validation checks source references, manual-only status, approval sections, fields, decision statuses, approver requirements, blocker disposition, risk acceptance, rollback readiness, monitoring readiness, decision lock conditions, evidence rules, stop conditions, and guardrails.
