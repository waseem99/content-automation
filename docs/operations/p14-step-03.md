# P14 Step 03

This step documents access certification expectations for production compliance and audit readiness.

Part of #196. Closes #199 after the PR merges.

## Goal

Create a repeatable access certification process that confirms production access inventory, reviewers, decisions, evidence, and closure criteria are complete before access review is marked ready.

## Source references

This runbook builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p14-step-02.md
docs/operations/p13-readiness-report.md
```

## Access inventory requirements

Each access certification cycle must inventory:

- repository access;
- deployment environment access;
- database access;
- object storage access;
- dashboard access;
- alert routing access;
- evidence archive access;
- operator tooling access;
- emergency access;
- service account access.

## Required inventory fields

Each inventory row must record:

- access surface;
- account or role name;
- access type;
- business justification;
- access owner;
- reviewer;
- approval status;
- last activity signal;
- evidence source;
- review date;
- next review date;
- removal action owner when access is not approved.

## Certification roles

Required roles:

- access certification owner;
- access surface owner;
- reviewer;
- evidence owner;
- removal action owner;
- exception owner;
- audit package owner.

Each role must have a primary owner and backup owner. Access rows without owners cannot be certified.

## Review cadence

Minimum cadence:

- access certification quarterly;
- emergency access review monthly;
- service account review quarterly;
- privileged access review monthly;
- access review after any material production change;
- access evidence review before audit package closeout.

## Certification decisions

Allowed certification decisions:

- access approved with current evidence;
- access removal required;
- access owner update required;
- justification refresh required;
- evidence refresh required;
- exception accepted with owner and expiry date;
- blocked because inventory is incomplete.

## Closure criteria

Access certification can close only when:

- inventory is complete;
- every access row has an owner;
- every access row has a reviewer;
- every approval decision has evidence;
- removal actions have owners and target review dates;
- accepted exceptions have owners and expiry dates;
- evidence archive entry is recorded;
- next review date is recorded.

## Stop conditions

Stop access certification closure if:

- access inventory is missing;
- access surface is missing;
- account or role name is missing;
- business justification is missing;
- access owner is missing;
- reviewer is missing;
- approval status is missing;
- evidence source is missing;
- removal action lacks owner;
- accepted exception lacks expiry date;
- evidence contains secret values;
- notes contain private runtime values;
- workflow gate bypass is requested.

## Guardrails

- No access review closure with missing inventory.
- No access certification closure without evidence.
- No ownerless production access row.
- No approval without reviewer.
- No accepted exception without owner and expiry date.
- No secret values in evidence.
- No private runtime values in notes.
- No automatic approval.
- No workflow gate bypass.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p14_step_03.py
```

The validation checks source references, inventory requirements, required fields, certification roles, cadence, decisions, closure criteria, stop conditions, and guardrails.
