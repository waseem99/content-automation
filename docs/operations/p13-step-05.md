# P13 Step 05

This step documents resilience drill cadence for production maturity and resilience.

Part of #183. Closes #188 after the PR merges.

## Goal

Create a recurring resilience drill process that tests recovery thinking, backup and restore evidence, failover readiness, capacity response, ownership, and action tracking.

## Source references

This runbook builds on:

```text
docs/operations/p13-step-01.md
docs/operations/p13-step-02.md
docs/operations/p13-step-03.md
docs/operations/p13-step-04.md
```

## Drill types

Maintain cadence for:

- disaster recovery tabletop drill;
- backup evidence review drill;
- restore validation drill;
- failover readiness drill;
- capacity threshold response drill;
- alert route drill;
- owner handoff drill;
- evidence archive drill.

## Drill cadence

Minimum cadence:

- disaster recovery tabletop quarterly;
- backup evidence drill monthly;
- restore validation drill quarterly;
- failover readiness drill quarterly;
- capacity threshold response drill quarterly;
- owner handoff drill after major ownership change;
- evidence archive drill before closeout.

## Required owners

Required roles:

- resilience drill owner;
- disaster recovery owner;
- backup owner;
- restore validation owner;
- failover owner;
- capacity planning owner;
- monitoring owner;
- incident review owner;
- evidence archive owner;
- decision owner.

Every role must have a primary owner and backup owner.

## Drill evidence

Each drill must record:

- drill ID;
- drill type;
- drill date;
- owner list;
- scenario summary;
- expected outcome;
- actual outcome;
- evidence source;
- observed gaps;
- action item list;
- evidence archive entry.

## Evaluation criteria

Evaluate:

- objective completion;
- owner response;
- evidence completeness;
- recovery objective alignment;
- backup and restore readiness;
- failover readiness;
- capacity threshold response;
- incident review follow-up;
- action closure status.

## Action tracking

Each action item must record:

- action title;
- owner;
- backup owner;
- due date;
- severity;
- validation method;
- completion evidence;
- next review date.

## Stop conditions

Stop drill closure if:

- drill owner is missing;
- required owner is missing;
- evidence source is missing;
- critical gap lacks action owner;
- action item lacks due date;
- validation method is missing;
- evidence contains secret values;
- workflow gate bypass is requested.

## Guardrails

- No drill closure without evidence.
- No critical gap without action owner.
- No action item without due date.
- No ownerless drill.
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
tests/integration/test_p13_step_05.py
```

The validation checks source references, drill types, cadence, owners, evidence, evaluation criteria, action tracking, stop conditions, and guardrails.
