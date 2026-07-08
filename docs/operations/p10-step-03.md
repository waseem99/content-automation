# P10 Step 03

This step documents controlled exposure and smoke testing for production rollout implementation.

Part of #144. Closes #147 after the PR merges.

## Goal

Define how limited production exposure is enabled, verified, and stopped if smoke checks or guardrails fail.

## Source references

This runbook builds on:

```text
docs/operations/p10-step-01.md
docs/operations/p10-step-02.md
docs/operations/p9-step-05.md
```

## Controlled exposure rules

Controlled exposure may begin only when:

- approved production exposure decision record exists;
- deployment execution checklist is complete;
- health and readiness checks passed;
- protected routes are verified;
- rollback owner is available;
- alert route is available;
- exposure window is recorded;
- smoke test owner is available.

## Exposure window

Record:

- start time;
- planned end time;
- decision owner;
- smoke test owner;
- rollback owner;
- monitoring owner;
- allowed audience or access boundary;
- rollback trigger threshold.

The first exposure window should stay limited and reversible.

## Smoke tests

Required smoke tests:

1. Confirm `GET /health` succeeds.
2. Confirm `GET /runtime/ready` returns `ok: true`.
3. Confirm `GET /runtime/config` returns safe configuration only.
4. Confirm `GET /runtime/observability` returns the telemetry contract.
5. Confirm protected routes reject unauthenticated access.
6. Confirm authenticated operator can read queue view.
7. Confirm authenticated operator can read dashboard queue view.
8. Confirm authenticated operator can read audit view.
9. Confirm dashboards receive health and readiness signals.
10. Confirm alert routing remains available.

## Rollback triggers

Rollback decision path must be used if any of these occur:

- health check fails;
- readiness check fails;
- protected route access is not enforced;
- config route exposes private runtime values;
- observability route is unavailable;
- repeated 5xx responses exceed threshold;
- queue route fails unexpectedly;
- audit route fails unexpectedly;
- alert route is unavailable;
- rollback owner becomes unavailable.

## Exposure hold points

Hold points:

- before enabling exposure;
- after first health and readiness pass;
- after protected route verification;
- after smoke test completion;
- before expanding beyond initial access boundary.

Each hold point requires human acknowledgement.

## Evidence capture

Record:

- decision record reference;
- deployment checklist reference;
- exposure window;
- access boundary;
- smoke test results;
- dashboard signal result;
- alert route result;
- rollback trigger review result;
- hold point acknowledgements;
- final exposure decision.

Do not record secrets, tokens, connection strings, raw operator keys, or private runtime values.

## Stop conditions

Stop controlled exposure if:

- decision record is missing;
- deployment checklist is incomplete;
- smoke test owner is unavailable;
- rollback owner is unavailable;
- alert route is unavailable;
- any required smoke test fails;
- any rollback trigger threshold is reached;
- evidence would expose secret values;
- workflow gate bypass is requested.

## Guardrails

- No exposure without approved decision record.
- No exposure expansion without smoke test pass.
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
tests/integration/test_p10_step_03.py
```

The validation checks source references, exposure rules, exposure window, smoke tests, rollback triggers, hold points, evidence, stop conditions, and guardrails.
