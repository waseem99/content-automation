# P12 Step 02

This step documents quarterly access review for production lifecycle governance.

Part of #170. Closes #172 after the PR merges.

## Goal

Create a recurring access review process for production systems, repositories, credentials, dashboards, alert routes, evidence archives, and operator roles.

## Source references

This runbook builds on:

```text
docs/operations/p12-step-01.md
docs/operations/p11-step-05.md
docs/operations/p11-step-04.md
```

## Review cadence

- Run once per quarter.
- Run after any major ownership change.
- Run after any high-severity access-related incident.
- Run before audit evidence packaging.
- Record completed review evidence in the production evidence archive.

## Access inventory

The review must cover:

- repository access;
- deployment access;
- database access;
- dashboard access;
- alert route access;
- evidence archive access;
- secret management access;
- production runtime access;
- emergency access;
- service account ownership.

## Required roles

Required roles:

- access review owner;
- decision owner;
- operations owner;
- security or guardrail reviewer;
- evidence archive owner;
- system owner for each reviewed surface.

Each role must have a primary owner and backup owner.

## Review evidence

Record for each reviewed access item:

- access item ID;
- access type;
- user, group, or service account;
- business justification;
- current owner;
- reviewer;
- decision;
- removal action if needed;
- exception link if retained;
- evidence archive entry.

## Review decisions

Allowed decisions:

- retain access;
- remove access;
- reduce access;
- move to service account ownership review;
- create time-limited exception;
- escalate for decision owner review.

## Removal tracking

Every removal must record:

- removal owner;
- due date;
- validation method;
- completion evidence;
- follow-up review date.

## Exception handling

Retained access that fails normal criteria requires:

- exception owner;
- reason;
- expiry date;
- compensating control;
- decision owner approval;
- next review date.

## Stop conditions

Stop review closure if:

- required surface is missing from inventory;
- reviewer is also the sole access owner;
- removal action lacks owner;
- exception lacks expiry date;
- emergency access lacks owner;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No access review closure with missing inventory.
- No permanent exception without expiry date.
- No reviewer-only approval for own access.
- No automatic approval.
- No workflow gate bypass.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p12_step_02.py
```

The validation checks source references, cadence, access inventory, roles, review evidence, decisions, removal tracking, exceptions, stop conditions, and guardrails.
