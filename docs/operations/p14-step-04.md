# P14 Step 04

This step documents production control testing expectations for compliance and audit readiness.

Part of #196. Closes #200 after the PR merges.

## Goal

Create a repeatable control testing process that records testing inputs, evidence, owners, result states, action tracking, and closure criteria for production controls.

## Source references

This runbook builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p14-step-02.md
docs/operations/p14-step-03.md
docs/operations/p13-readiness-report.md
```

## Control testing inputs

Each control test must review:

- compliance evidence map;
- access certification evidence;
- security review evidence;
- operational runbook evidence;
- incident and action tracking evidence;
- backup and restore evidence;
- failover readiness evidence;
- capacity planning evidence;
- resilience drill evidence;
- CI validation evidence;
- open exception evidence.

## Required control fields

Each control test row must record:

- control identifier;
- control area;
- control objective;
- test procedure;
- evidence source;
- evidence owner;
- control owner;
- tester;
- reviewer;
- test date;
- result state;
- action owner;
- target review date;
- evidence archive entry.

## Required owners

Required roles:

- control owner;
- test owner;
- reviewer;
- evidence owner;
- action owner;
- exception owner;
- audit package owner.

Each owner must have a primary owner and backup owner. Control testing cannot close with ownerless failures, ownerless exceptions, or ownerless evidence.

## Result states

Allowed result states:

- pass with current evidence;
- pass with observation;
- corrective action required;
- evidence refresh required;
- retest required;
- exception accepted with owner and expiry date;
- blocked because evidence is missing.

## Action tracking

Failed or incomplete control tests must record:

- finding summary;
- action owner;
- target review date;
- evidence required for closure;
- current action status;
- escalation owner when overdue;
- retest requirement;
- final reviewer decision.

## Review cadence

Minimum cadence:

- control testing quarterly;
- high-risk control testing monthly;
- access control testing quarterly;
- security control testing monthly;
- resilience control testing quarterly;
- control evidence review before audit package closeout;
- retest after corrective action completion.

## Closure criteria

A control can close only when:

- test procedure is documented;
- evidence source is recorded;
- evidence owner is recorded;
- tester and reviewer are recorded;
- result state is recorded;
- failed or incomplete result has an action owner;
- accepted exception has owner and expiry date;
- evidence archive entry is recorded.

## Stop conditions

Stop control closure if:

- control objective is missing;
- test procedure is missing;
- evidence source is missing;
- evidence owner is missing;
- tester is missing;
- reviewer is missing;
- result state is missing;
- failed or incomplete result lacks action owner;
- accepted exception lacks expiry date;
- retest requirement is missing after corrective action;
- evidence contains secret values;
- notes contain private runtime values;
- workflow gate bypass is requested.

## Guardrails

- No control closure without evidence.
- No control testing closure without tester and reviewer.
- No failed or incomplete control test without action owner.
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
tests/integration/test_p14_step_04.py
```

The validation checks source references, testing inputs, required fields, ownership, result states, action tracking, cadence, closure criteria, stop conditions, and guardrails.
