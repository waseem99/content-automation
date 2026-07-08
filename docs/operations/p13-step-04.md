# P13 Step 04

This step documents capacity planning for production maturity and resilience.

Part of #183. Closes #187 after the PR merges.

## Goal

Create a recurring capacity planning process that records capacity signals, thresholds, owners, forecast cadence, scaling decisions, evidence, and stop conditions.

## Source references

This runbook builds on:

```text
docs/operations/p12-step-03.md
docs/operations/p13-step-03.md
docs/operations/p13-step-01.md
```

## Capacity signals

Track signals for:

- request volume;
- error rate;
- response latency;
- worker queue depth;
- database connection pressure;
- database storage growth;
- object storage growth;
- CPU or memory pressure;
- workflow duration;
- alert volume.

## Thresholds

Each threshold must record:

- signal name;
- current baseline;
- warning threshold;
- critical threshold;
- owner;
- backup owner;
- evidence source;
- last review date;
- next review date;
- corrective action trigger.

## Required owners

Required roles:

- capacity planning owner;
- operations owner;
- monitoring owner;
- database owner;
- workflow owner;
- deployment owner;
- decision owner;
- evidence archive owner.

Each role must have a primary owner and backup owner.

## Forecast cadence

Minimum cadence:

- monthly capacity review;
- quarterly forecast update;
- review after major incident;
- review before significant exposure expansion;
- review after critical threshold breach;
- review before P13 closeout.

## Scaling decisions

Allowed scaling decisions:

- no change required;
- tune threshold;
- add capacity;
- reduce capacity;
- optimize workload;
- request architecture review;
- open corrective action;
- accept documented risk with owner and expiry date.

## Evidence requirements

Each capacity review must record:

- review date;
- reviewed signals;
- threshold status;
- trend summary;
- forecast assumption;
- scaling decision;
- owner signoff;
- action item list;
- evidence archive entry.

## Stop conditions

Stop capacity review closure if:

- capacity owner is missing;
- critical signal lacks threshold;
- critical threshold breach lacks action owner;
- forecast assumption is missing;
- accepted risk lacks expiry date;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No capacity review closure without evidence.
- No critical threshold breach without action owner.
- No accepted capacity risk without expiry date.
- No ownerless capacity signal.
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
tests/integration/test_p13_step_04.py
```

The validation checks source references, signals, thresholds, owners, forecast cadence, scaling decisions, evidence requirements, stop conditions, and guardrails.
