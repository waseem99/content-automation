# P18 Step 05

This step documents the runbook index and ownership map for P14-P18 operational handover.

Part of #248. Closes #253 after the PR merges.

## Goal

Create one central index of operational runbooks, owners, reviewers, review cadence, evidence expectations, update routes, ownership gaps, stale-document handling, and guardrails for handover continuity.

## Source references

This ownership map builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p14-step-06.md
docs/operations/p15-readiness-report.md
docs/operations/p16-readiness-report.md
docs/operations/p17-readiness-report.md
docs/operations/p18-step-01.md
docs/operations/p18-step-02.md
docs/operations/p18-step-03.md
docs/operations/p18-step-04.md
```

## Index status

This index is documentation-only.

It does not:

- assign live production access;
- approve production launch;
- schedule production launch;
- execute review automation;
- publish runbook material;
- render ownership material;
- export runbook evidence;
- bypass workflow gates;
- replace scoped issues and PRs.

## Indexed runbook groups

The index must cover:

- P14 compliance and audit readiness runbooks;
- P15 continuous improvement runbooks;
- P16 observability and operating metrics runbooks;
- P17 release readiness and controlled launch runbooks;
- P18 handover and operator enablement runbooks;
- final readiness reports;
- closeout checklists;
- validation tests.

## Required index fields

Each runbook entry must record:

- runbook identifier;
- runbook path;
- phase;
- purpose;
- owner;
- reviewer;
- backup owner;
- review cadence;
- last review placeholder;
- next review placeholder;
- evidence expectation;
- evidence sensitivity;
- update route;
- escalation route;
- stale status;
- closure criteria.

## Ownership roles

Allowed ownership roles:

- documentation owner;
- operator owner;
- reviewer;
- support owner;
- release owner;
- observability owner;
- evidence owner;
- incident owner;
- backup owner.

## Review cadence

Allowed review cadence values:

- per PR closeout;
- weekly during active rollout;
- monthly during steady operation;
- after incident;
- after release decision;
- after support pattern;
- after guardrail change;
- before phase closeout.

## Update routes

Allowed update routes:

- no update required;
- update existing runbook;
- create implementation issue;
- create documentation issue;
- route to evidence owner;
- route to support owner;
- route to release owner;
- route to incident owner;
- route to operator owner;
- block by guardrail;
- reject with reason.

## Evidence expectations

Runbook evidence may include:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized review notes;
- summarized update notes;
- summarized owner notes;
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
- rendered runbook materials;
- scheduled ownership outputs.

## Ownership gap handling

A runbook has an ownership gap when:

- owner is missing;
- reviewer is missing;
- backup owner is missing;
- review cadence is missing;
- evidence expectation is missing;
- update route is missing;
- escalation route is missing;
- stale status is unknown.

Ownership gaps must route to documentation owner before closeout.

## Stale runbook handling

A runbook is stale when:

- review cadence is missed;
- referenced issue or PR is obsolete;
- ownership no longer matches current role map;
- guardrail language is missing;
- evidence rules are incomplete;
- support or incident route is outdated;
- release-readiness dependency is outdated;
- validation test reference is missing.

Stale runbooks must receive an action route before closeout.

## Minimum P18 ownership map

| Runbook | Owner role | Reviewer role | Cadence | Update route |
| --- | --- | --- | --- | --- |
| `docs/operations/p18-step-01.md` | operator owner | reviewer | monthly during steady operation | update existing runbook |
| `docs/operations/p18-step-02.md` | documentation owner | reviewer | after guardrail change | update existing runbook |
| `docs/operations/p18-step-03.md` | documentation owner | reviewer | before phase closeout | update existing runbook |
| `docs/operations/p18-step-04.md` | support owner | reviewer | after support pattern | update existing runbook |
| `docs/operations/p18-step-05.md` | documentation owner | evidence owner | monthly during steady operation | update existing runbook |

## Stop conditions

Stop ownership map closure if:

- runbook path is missing;
- owner is missing;
- reviewer is missing;
- review cadence is missing;
- evidence expectation is missing;
- update route is missing;
- escalation route is missing;
- ownership gap has no action route;
- stale runbook has no action route;
- validation test reference is missing;
- automatic approval is implied;
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
tests/integration/test_p18_step_05.py
```

The validation checks source references, documentation-only status, indexed groups, required fields, ownership roles, review cadence, update routes, evidence expectations, ownership gap handling, stale runbook handling, minimum ownership map, stop conditions, and guardrails.
