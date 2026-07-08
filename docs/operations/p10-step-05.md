# P10 Step 05

This step documents the first production incident drill for controlled rollout implementation.

Part of #144. Closes #149 after the PR merges.

## Goal

Rehearse the first production incident response path after controlled rollout implementation, without causing live user impact.

## Source references

This drill builds on:

```text
docs/operations/p10-step-04.md
docs/operations/p10-step-03.md
docs/operations/p9-step-03.md
docs/operations/p9-step-04.md
```

## Drill scenario

Default drill scenario:

- readiness degradation is detected after controlled exposure;
- dashboard shows readiness anomaly;
- alert route is used;
- rollback owner joins;
- decision owner evaluates rollback threshold;
- rollback decision is recorded;
- lessons learned are captured.

The drill must not create a real outage or require live production rollback.

## Required roles

Required roles:

- incident commander;
- decision owner;
- deployment operator;
- database operator;
- rollback owner;
- monitoring owner;
- alert routing owner;
- evidence recorder.

## Drill timeline

Recommended timeline:

1. Start drill and confirm scope.
2. Announce simulated symptom.
3. Confirm dashboard signal path.
4. Confirm alert routing path.
5. Confirm incident owner and decision owner.
6. Review rollback decision path.
7. Review customer or stakeholder communication path.
8. Record simulated decision.
9. Record gaps and owners.
10. End drill and publish internal notes.

## Escalation checks

Confirm escalation path for:

- healthcheck failure;
- readiness failure;
- repeated 5xx responses;
- database connection failure;
- migration readiness failure;
- protected route access anomaly;
- queue growth;
- audit route failure;
- missing observability contract.

## Rollback decision review

Rollback decision review must confirm:

- rollback owner is available;
- previous known-good image is known;
- previous known-good configuration source is known;
- backup state is known;
- restore path is understood;
- forward-fix option is considered;
- decision owner records the final decision.

## Evidence capture

Record:

- drill date;
- scenario used;
- participants by role;
- alert route result;
- dashboard review result;
- rollback decision result;
- escalation gaps;
- communication gaps;
- action items with owners;
- follow-up date.

Do not record secrets, tokens, connection strings, raw operator keys, or private runtime values.

## Stop conditions

Stop the drill if:

- drill creates real user impact;
- live rollback is requested without explicit production decision;
- alert route owner is unavailable;
- rollback owner is unavailable;
- evidence would expose secret values;
- workflow gate bypass is requested.

## Guardrails

- No real user impact from the drill.
- No live rollback without explicit decision.
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
tests/integration/test_p10_step_05.py
```

The validation checks source references, scenario, roles, timeline, escalation, rollback decision review, evidence, stop conditions, and guardrails.
