# P13 Step 02

This step documents backup and restore evidence for production maturity and resilience.

Part of #183. Closes #185 after the PR merges.

## Goal

Create a recurring evidence process for backup inventory, restore validation, owners, verification cadence, retention, and stop conditions.

## Source references

This runbook builds on:

```text
docs/operations/p13-step-01.md
docs/operations/p12-step-04.md
docs/operations/p12-readiness-report.md
```

## Backup inventory

Track backups for:

- production database;
- migration state;
- configuration records;
- evidence archive records;
- deployment configuration;
- object storage;
- audit records;
- monitoring configuration;
- alert routing configuration;
- service ownership records.

## Required fields

Each backup entry must record:

- backup ID;
- protected surface;
- backup owner;
- backup location reference;
- backup cadence;
- retention class;
- last successful backup date;
- last restore validation date;
- restore validation owner;
- evidence archive entry.

## Restore evidence

Restore evidence must record:

- restore test date;
- source backup ID;
- restore target;
- validation method;
- validation result;
- data integrity check;
- owner signoff;
- observed gaps;
- corrective actions;
- evidence archive entry.

## Verification cadence

Minimum cadence:

- backup inventory review monthly;
- backup completion evidence review monthly;
- restore validation at least quarterly;
- retention review quarterly;
- restore evidence review after any backup failure;
- closeout evidence review before P13 closeout.

## Retention rules

Retention rules:

- retention class must be recorded;
- disposal must not remove active incident evidence;
- disposal must not remove active audit evidence;
- disposal must have evidence archive owner approval;
- retained evidence must not include raw secret values.

## Review decisions

Allowed decisions:

- backup evidence accepted;
- restore evidence accepted;
- restore validation required;
- retention update required;
- corrective action required;
- risk accepted with owner and expiry date.

## Stop conditions

Stop closure if:

- backup owner is missing;
- restore validation owner is missing;
- backup evidence is missing;
- restore evidence is missing;
- retention class is missing;
- validation failed without corrective action;
- accepted risk lacks expiry date;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No backup review closure without evidence.
- No restore review closure without validation evidence.
- No ownerless backup entry.
- No retained secret values in evidence.
- No evidence disposal without approval.
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
tests/integration/test_p13_step_02.py
```

The validation checks source references, backup inventory, required fields, restore evidence, verification cadence, retention rules, review decisions, stop conditions, and guardrails.
