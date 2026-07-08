# P10 Step 02

This step documents production deployment checklist execution for controlled rollout implementation.

Part of #144. Closes #146 after the PR merges.

## Goal

Provide a checklist for executing a controlled production deployment only after the production exposure decision record is approved.

## Source references

This checklist builds on:

```text
docs/operations/p10-step-01.md
docs/operations/p9-step-01.md
docs/operations/p9-step-05.md
```

## Required prerequisites

Before deployment execution:

- approved production exposure decision record exists;
- exact commit SHA is recorded;
- exact image tag or digest is recorded;
- latest exact-head CI is green;
- rollback owner is available;
- backup availability is confirmed;
- deployment operator is available;
- database operator is available;
- monitoring reviewer is available;
- stop conditions are reviewed.

## Pre-deploy checklist

Complete before deploying:

1. Confirm decision state is go or go with documented limitations.
2. Confirm limitations do not affect health, readiness, backup, restore, rollback, protected routes, workflow gates, or secret handling.
3. Confirm deployment target is production.
4. Confirm rollout window is approved.
5. Confirm previous known-good image is recorded.
6. Confirm previous known-good configuration source is recorded.
7. Confirm backup reference is recorded.
8. Confirm dashboard and alert routes are available.
9. Confirm protected route verification plan is ready.
10. Confirm no public exposure begins before the hold point.

## Deployment execution checklist

Execution steps:

1. Set deployment status to in progress.
2. Deploy the approved image tag or digest.
3. Apply approved production configuration from secret-managed sources.
4. Keep exposure private until smoke checks pass.
5. Confirm process starts successfully.
6. Confirm `GET /health` succeeds.
7. Confirm `GET /runtime/ready` returns `ok: true`.
8. Confirm `GET /runtime/config` returns safe configuration only.
9. Confirm `GET /runtime/observability` returns the telemetry contract.
10. Confirm protected routes require operator access.
11. Confirm no secret values appear in logs.
12. Record the deployment result.

## Hold points

Deployment must stop at these hold points:

- before applying production configuration;
- before any public exposure;
- after health and readiness checks;
- after protected route verification;
- before declaring rollout go-live complete.

Each hold point requires human acknowledgement.

## Verification checks

Required verification:

- exact image tag or digest deployed;
- production configuration source confirmed;
- health route passed;
- readiness route passed;
- config route excludes secrets;
- observability route available;
- protected routes reject unauthenticated access;
- dashboard signals visible;
- alert route available;
- rollback path remains available.

## Stop conditions

Stop deployment and use rollback decision path if:

- approved decision record is missing;
- latest exact-head CI is not green;
- image tag or digest does not match approval;
- health check fails;
- readiness check fails;
- protected routes are not protected;
- config route exposes private values;
- alert route is unavailable;
- rollback owner is unavailable;
- workflow gate bypass is required.

## Evidence capture

Record:

- decision record reference;
- deployment timestamp;
- commit SHA;
- image tag or digest;
- production configuration source reference;
- health result;
- readiness result;
- protected route result;
- dashboard signal result;
- alert route result;
- hold point acknowledgements;
- next action.

Do not record secrets, tokens, connection strings, raw operator keys, or private runtime values.

## Guardrails

- No deployment without approved decision record.
- No public exposure before smoke checks pass.
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
tests/integration/test_p10_step_02.py
```

The validation checks source references, prerequisites, pre-deploy steps, execution, hold points, verification, stop conditions, evidence, and guardrails.
