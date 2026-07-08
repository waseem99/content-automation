# P8 Step 04

This step documents rollback expectations for app image, configuration, and database migration safety.

Part of #118. Closes #122 after the PR merges.

## Goal

Give operators a provider-neutral rollback runbook for controlled deployment recovery without choosing a specific deployment platform.

## Rollback decision points

Start rollback review when any of these occur after deployment:

- liveness failure;
- readiness failure;
- repeated 5xx responses;
- database connection failures;
- migration readiness failure;
- protected route access failure;
- operator workflow gate behavior changes;
- unexpected queue or audit route failure.

## Rollback roles

Rollback requires:

- decision owner;
- deployment operator;
- database operator when database state is involved;
- reviewer to confirm final checks.

## Application image rollback

Application rollback steps:

1. Identify current image tag or digest.
2. Identify previous known-good image tag or digest.
3. Confirm previous image uses compatible database schema.
4. Stop routing new traffic to the failing runtime instance.
5. Deploy the previous known-good image.
6. Confirm `GET /health` succeeds.
7. Confirm `GET /runtime/ready` returns `ok: true`.
8. Confirm `GET /runtime/observability` returns the contract.
9. Confirm protected routes still require operator access.
10. Record rollback result.

## Configuration rollback

Configuration rollback steps:

1. Identify changed configuration values.
2. Identify previous known-good configuration source.
3. No secret values are written to logs or issue comments.
4. Reapply previous known-good configuration.
5. Restart or recycle the runtime instance if required.
6. Confirm `GET /runtime/config` returns safe expected values only.
7. Confirm `GET /runtime/ready` returns `ok: true`.
8. Record rollback result.

## Database migration safety

Database rollback must be handled conservatively.

Rules:

- prefer forward-fix migration when safe;
- do not run destructive database rollback without an approved restore plan;
- confirm a fresh current-state backup exists before any restore;
- confirm backup checksum before restore;
- confirm target environment before restore;
- run migration status check after restore;
- confirm application image compatibility with restored schema.

Reference:

```text
docs/operations/p8-step-03.md
```

## Traffic handling

During rollback:

- remove unready instances from serving traffic;
- do not route traffic to an instance with readiness failure;
- keep protected operator routes behind access controls;
- do not bypass workflow gates to recover faster.

## Post-rollback verification

After rollback:

1. Confirm `GET /health` succeeds.
2. Confirm `GET /runtime/config` returns safe configuration only.
3. Confirm `GET /runtime/ready` returns `ok: true`.
4. Confirm `GET /runtime/observability` returns the contract.
5. Confirm protected routes still require operator access.
6. Confirm queue route can read expected data.
7. Confirm audit route can read expected data.
8. Record root cause, fix owner, and follow-up action.

## Rollback completion criteria

Rollback is complete only when:

- service is healthy;
- readiness is true;
- expected configuration is active;
- database state is verified;
- protected routes remain protected;
- workflow gates are not bypassed;
- operator notes record the final state.

## Out of scope

This step does not choose:

- deployment vendor;
- orchestration platform;
- traffic manager;
- database vendor;
- incident management vendor.

## Guardrails

- No rollback without a decision owner.
- No database restore without fresh backup confirmation.
- No secret values in logs.
- No private runtime values in rollback notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.
- No public production launch.

## Validation

Covered by:

```text
tests/integration/test_p8_step_04.py
```

The validation checks rollback decision points, image rollback, configuration rollback, database safety, traffic handling, verification, completion criteria, out-of-scope boundaries, and guardrails.
