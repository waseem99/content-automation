# P18 Step 02

This step documents role-based operating procedures for production handover and operator enablement.

Part of #248. Closes #250 after the PR merges.

## Goal

Define what each handover role can do, cannot do, must escalate, and must record so production operations remain controlled after P17 release readiness.

## Source references

These procedures build on:

```text
docs/operations/p18-step-01.md
docs/operations/p17-readiness-report.md
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p17-step-03.md
docs/operations/p17-step-04.md
docs/operations/p17-step-05.md
docs/operations/p16-readiness-report.md
docs/operations/p15-readiness-report.md
docs/operations/p14-step-06.md
```

## Procedure status

These procedures are documentation-only.

They do not:

- grant production access;
- approve production launch;
- schedule production launch;
- execute release activities;
- bypass workflow gates;
- replace manual approval;
- publish operating material;
- render training material;
- export role evidence;
- override support escalation.

## Role catalog

The operating model includes these roles:

- admin;
- reviewer;
- operator;
- support owner;
- release owner;
- incident owner;
- evidence owner;
- documentation owner.

## Admin procedure

Admin may:

- maintain repository settings when approved;
- manage workflow configuration through scoped PRs;
- review access-related requests;
- route permission issues;
- confirm branch protection expectations;
- request evidence from owners.

Admin must not:

- bypass exact-head CI;
- merge failing PRs;
- approve release without named approvers;
- store secret values in evidence;
- expose private runtime values;
- publish or export restricted material.

Admin must escalate when:

- billing or runner constraints block CI;
- workflow configuration cannot start;
- branch protection conflicts appear;
- restricted evidence is detected;
- access request has no owner.

## Reviewer procedure

Reviewer may:

- review scoped PRs;
- confirm acceptance criteria;
- check documentation completeness;
- verify guardrails are present;
- request changes before merge;
- confirm exact-head CI before approval notes.

Reviewer must not:

- approve out-of-scope changes;
- approve missing evidence;
- approve automatic launch language;
- approve unresolved blockers as completed;
- approve restricted values in evidence.

Reviewer must escalate when:

- PR scope expands;
- acceptance criteria are unclear;
- required evidence is missing;
- human approval is implied but not named;
- workflow gate bypass is requested.

## Operator procedure

Operator may:

- perform daily checks;
- monitor open issues and PRs;
- record summarized operator notes;
- follow handover action routes;
- escalate support or incident signals;
- confirm issue closure after merge.

Operator must not:

- merge without required green checks;
- change workflow gates without scoped issue;
- make release decisions alone;
- schedule launch activity;
- publish, render, or export handover material;
- store customer data exports.

Operator must escalate when:

- exact-head CI fails;
- daily check finds ownerless work;
- incident signal appears;
- support signal needs owner;
- release decision is requested;
- restricted evidence appears.

## Support owner procedure

Support owner may:

- triage support cases;
- assign support action owners;
- summarize support evidence;
- route incidents to incident owner;
- request operator context;
- identify repeated support patterns.

Support owner must not:

- export customer data;
- store raw private runtime logs;
- publish support evidence;
- bypass incident escalation;
- close support cases without evidence source.

Support owner must escalate when:

- severity is unclear;
- customer impact is suspected;
- support volume spikes;
- rollback trigger is suggested;
- evidence contains restricted values.

## Release owner procedure

Release owner may:

- manage release decision handoff;
- confirm release calendar entry;
- confirm blackout window status;
- coordinate go/no-go approval record;
- verify rollback readiness;
- verify monitoring readiness.

Release owner must not:

- approve release from CI alone;
- launch without named approval;
- launch during blackout window;
- bypass release checklist;
- bypass dry-run rehearsal;
- bypass post-release observation plan.

Release owner must escalate when:

- required approver is missing;
- blackout conflict appears;
- rollback readiness is missing;
- monitoring readiness is missing;
- unresolved blocker has no disposition.

## Incident owner procedure

Incident owner may:

- classify incident severity;
- assign incident action owners;
- coordinate escalation route;
- recommend rollback decision review;
- summarize incident evidence;
- define closure criteria.

Incident owner must not:

- expose private runtime values;
- store raw credentials;
- export incident packages externally;
- close incident without evidence source;
- suppress escalation when stop condition is met.

Incident owner must escalate when:

- severity is high or critical;
- repeated incident pattern appears;
- rollback trigger is met;
- evidence source is missing;
- customer data export is requested.

## Evidence owner procedure

Evidence owner may:

- validate allowed evidence types;
- reject restricted evidence;
- confirm evidence sensitivity;
- maintain evidence archive entry names;
- request redaction or replacement.

Evidence owner must not:

- store secret values;
- store production tokens;
- store private environment dumps;
- store customer data exports;
- store raw logs with restricted values;
- approve external package exports.

Evidence owner must escalate when:

- evidence contains restricted values;
- evidence source is missing;
- evidence sensitivity is unclear;
- external export is requested;
- evidence retention route is missing.

## Documentation owner procedure

Documentation owner may:

- maintain runbooks;
- record document owners;
- track review cadence;
- route stale documents;
- request updates from role owners;
- maintain closeout references.

Documentation owner must not:

- close stale runbooks without owner review;
- publish documentation externally;
- render training material without approval;
- remove guardrails;
- hide known gaps.

Documentation owner must escalate when:

- runbook owner is missing;
- review cadence is missing;
- stale document has no action route;
- guardrail language is removed;
- closeout evidence is incomplete.

## Required role record fields

Each role record must include:

- role identifier;
- role name;
- role owner;
- reviewer;
- allowed actions;
- prohibited actions;
- required escalation triggers;
- required evidence;
- evidence sensitivity;
- action route;
- stop condition;
- validation requirement;
- closure criteria.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized role notes;
- summarized reviewer notes;
- summarized operator notes;
- summarized support notes;
- summarized incident notes;
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
- rendered operating materials;
- scheduled role outputs.

## Stop conditions

Stop procedure closure if:

- role owner is missing;
- reviewer is missing;
- allowed actions are missing;
- prohibited actions are missing;
- escalation triggers are missing;
- evidence source is missing;
- evidence sensitivity is missing;
- stop condition is missing;
- automatic approval is implied;
- production launch is implied;
- workflow gate bypass is requested;
- release calendar is missing for release decision;
- blackout check is missing for release decision;
- restricted evidence is present;
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
tests/integration/test_p18_step_02.py
```

The validation checks source references, documentation-only status, role catalog, role-specific procedures, required role record fields, evidence rules, stop conditions, and guardrails.
