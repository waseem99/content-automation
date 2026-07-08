# P14 Step 02

This step documents the recurring security review cadence for production compliance and audit readiness.

Part of #196. Closes #198 after the PR merges.

## Goal

Create a repeatable security review process that records review frequency, inputs, owners, outputs, escalation expectations, and evidence requirements without storing unsafe runtime or secret material.

## Source references

This runbook builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p13-readiness-report.md
docs/operations/p13-closeout-checklist.md
```

## Review cadence

Minimum cadence:

- security evidence review monthly;
- dependency and package review monthly;
- access-sensitive surface review quarterly;
- incident action review monthly;
- security review after any material production change;
- pre-audit security review before audit package closeout.

## Review inputs

Each security review must inspect:

- compliance evidence map status;
- open security findings;
- dependency update evidence;
- runtime configuration change evidence;
- access review evidence;
- incident and action tracking evidence;
- dashboard and alert routing evidence;
- backup, restore, and failover evidence;
- accepted exceptions and expiry dates;
- prior review actions.

## Required owners

Required roles:

- security review owner;
- evidence owner;
- control owner;
- dependency owner;
- runtime configuration owner;
- access review owner;
- alert routing owner;
- action owner;
- exception owner.

Each owner must have a primary owner and backup owner. Reviews cannot close with ownerless findings or ownerless actions.

## Review outputs

Each review must produce:

- review date;
- reviewer names or roles;
- reviewed evidence list;
- decision summary;
- open finding list;
- action tracker updates;
- accepted exception list;
- expiry dates for accepted exceptions;
- next review date;
- evidence archive entry.

## Escalation expectations

Escalate when:

- high-severity finding has no action owner;
- action owner misses the agreed review date;
- secret value appears in evidence;
- private runtime value appears in notes;
- accepted exception lacks expiry date;
- access evidence is incomplete;
- alert routing owner is missing;
- workflow gate bypass is requested.

Escalated items must record an action owner, target review date, current status, and evidence archive reference.

## Review decisions

Allowed decisions:

- security posture accepted with current evidence;
- corrective action required;
- evidence refresh required;
- access review required;
- alert routing update required;
- dependency update required;
- exception accepted with owner and expiry date;
- audit package update required.

## Stop conditions

Stop review closure if:

- reviewed evidence list is missing;
- security review owner is missing;
- evidence owner is missing;
- high-severity finding has no action owner;
- accepted exception lacks expiry date;
- dependency update evidence is missing;
- access evidence is incomplete;
- evidence contains secret values;
- notes contain private runtime values;
- workflow gate bypass is requested.

## Guardrails

- No security review closure without reviewed evidence.
- No ownerless high-severity finding.
- No accepted exception without owner and expiry date.
- No access review closure with missing inventory.
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
tests/integration/test_p14_step_02.py
```

The validation checks source references, cadence, inputs, owners, outputs, escalation expectations, review decisions, stop conditions, and guardrails.
