# P14 Step 01

This step documents compliance evidence mapping for production compliance and audit readiness.

Part of #196. Closes #197 after the PR merges.

## Goal

Create an audit-ready evidence map that shows which production controls have evidence, who owns each evidence source, how often it is reviewed, and what stops a control from being marked ready.

## Source references

This runbook builds on:

```text
docs/operations/p13-readiness-report.md
docs/operations/p13-closeout-checklist.md
docs/operations/p13-step-01.md
docs/operations/p13-step-02.md
docs/operations/p13-step-03.md
docs/operations/p13-step-04.md
docs/operations/p13-step-05.md
```

## Evidence categories

Maintain an evidence map for:

- production governance evidence;
- access review evidence;
- security review evidence;
- operational runbook evidence;
- incident and action tracking evidence;
- backup and restore evidence;
- failover readiness evidence;
- capacity planning evidence;
- resilience drill evidence;
- control testing evidence;
- audit package evidence.

## Evidence map fields

Each evidence row must record:

- control area;
- control objective;
- evidence source;
- evidence owner;
- review owner;
- evidence cadence;
- evidence location;
- latest review date;
- next review date;
- open action owner;
- expiry date for accepted exception;
- readiness status.

## Evidence source rules

Evidence sources must be safe to store and review. Use:

- runbook references;
- merged PR references;
- CI run identifiers;
- issue references;
- checklist status;
- owner names or roles;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- customer data exports;
- external package exports.

## Ownership expectations

Required ownership fields:

- evidence owner;
- review owner;
- control owner;
- action owner;
- exception owner;
- audit package owner.

Each owner must have a primary owner and backup owner. Ownerless evidence cannot be used to close a control.

## Review cadence

Minimum cadence:

- compliance evidence mapping review monthly;
- access evidence review quarterly;
- security evidence review monthly;
- control testing evidence review quarterly;
- audit package evidence review before closeout;
- evidence review after any material production change.

## Readiness states

Allowed readiness states:

- ready with current evidence;
- corrective action required;
- evidence refresh required;
- owner update required;
- exception accepted with owner and expiry date;
- blocked because evidence is missing.

## Stop conditions

Stop evidence closure if:

- evidence source is missing;
- evidence owner is missing;
- review owner is missing;
- control objective is missing;
- latest review date is missing;
- open action lacks owner;
- accepted exception lacks expiry date;
- evidence contains secret values;
- evidence contains private runtime values;
- external export is requested;
- workflow gate bypass is requested.

## Guardrails

- No control closure without evidence.
- No evidence closure without owner and review owner.
- No accepted exception without owner and expiry date.
- No access review closure with missing inventory.
- No secret values in evidence.
- No private runtime values in notes.
- No external export.
- No automatic approval.
- No workflow gate bypass.
- No publishing.
- No scheduling.
- No rendering.

## Validation

Covered by:

```text
tests/integration/test_p14_step_01.py
```

The validation checks source references, evidence categories, map fields, safe source rules, ownership expectations, review cadence, readiness states, stop conditions, guardrails, and P14 CI wildcard coverage.
