# P12 Step 04

This step documents audit-ready production controls for production lifecycle governance.

Part of #170. Closes #174 after the PR merges.

## Goal

Create a lightweight production control inventory that maps governance controls to owners, evidence, review cadence, exceptions, and signoff.

## Source references

This runbook builds on:

```text
docs/operations/p12-step-02.md
docs/operations/p12-step-03.md
docs/operations/p11-step-04.md
docs/operations/p11-step-05.md
```

## Control inventory

Track controls for:

- release approval;
- rollback readiness;
- access review;
- alert routing;
- incident review;
- evidence archive indexing;
- owner and backup coverage;
- secret redaction;
- exception expiry;
- audit evidence retention.

## Control fields

Each control must record:

- control ID;
- control name;
- control objective;
- owner;
- backup owner;
- evidence source;
- review cadence;
- status;
- exception link if applicable;
- last review date;
- next review date.

## Evidence mapping

Evidence mapping must include:

- linked issue or PR;
- source runbook;
- evidence archive entry;
- related KPI if applicable;
- reviewer;
- signoff date;
- retained evidence location.

## Review cadence

Review controls:

- quarterly with access review;
- monthly with KPI reporting for critical controls;
- after major incident;
- after governance exception approval;
- before external audit packaging;
- before P12 closeout.

## Signoff rules

Control signoff requires:

- control owner confirmation;
- evidence archive owner confirmation;
- decision owner acceptance for critical controls;
- exception owner signoff when an exception exists;
- reviewer note for incomplete controls.

## Exception rules

A control exception must include:

- exception owner;
- reason;
- affected control;
- compensating control;
- expiry date;
- next review date;
- decision owner approval.

## Stop conditions

Stop control closure if:

- control owner is missing;
- evidence source is missing;
- critical control has no decision owner acceptance;
- exception lacks expiry date;
- compensating control is missing;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No control closure without evidence.
- No critical control signoff without decision owner acceptance.
- No exception without expiry date.
- No missing compensating control for exception.
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
tests/integration/test_p12_step_04.py
```

The validation checks source references, inventory, fields, evidence mapping, review cadence, signoff rules, exception rules, stop conditions, and guardrails.
