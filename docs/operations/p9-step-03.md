# P9 Step 03

This step documents a rollback rehearsal for application image, configuration, and database safety.

Part of #131. Closes #134 after the PR merges.

## Goal

Rehearse rollback decision making and recovery mechanics without impacting public production traffic.

## Source references

This runbook builds on:

```text
docs/operations/p8-step-04.md
docs/operations/p9-step-01.md
docs/operations/p9-step-02.md
```

## Rehearsal scope

The rollback rehearsal covers:

- rollback role confirmation;
- rollback decision point review;
- previous image identification;
- configuration rollback rehearsal;
- database restore decision rehearsal;
- traffic isolation rehearsal;
- health and readiness verification;
- evidence capture and exit criteria.

The rehearsal must not bypass workflow gates or launch public production traffic.

## Participants

Recommended participants:

- decision owner;
- deployment operator;
- database operator;
- reviewer for evidence;
- alert or dashboard reviewer.

## Preparation checklist

Before rollback rehearsal:

1. Confirm current candidate image tag or digest.
2. Confirm previous known-good image tag or digest.
3. Confirm previous known-good configuration source.
4. Confirm database backup is available.
5. Confirm restore rehearsal evidence is available.
6. Confirm rollback owner is available.
7. Confirm protected routes are still protected.
8. Confirm rehearsal target is private or internal.
9. Confirm traffic can be isolated from the rehearsal target.
10. Confirm no workflow gate bypass is needed.

## Decision points

Rollback decision review should include:

- liveness failure;
- readiness failure;
- repeated 5xx responses;
- database connection failure;
- migration readiness failure;
- protected route access anomaly;
- queue route failure;
- audit route failure;
- missing observability contract;
- unsafe configuration exposure.

## Execution steps

Rollback rehearsal steps:

1. Mark the rehearsal target as isolated.
2. Record the candidate image tag or digest.
3. Record the previous known-good image tag or digest.
4. Rehearse switching to the previous known-good image.
5. Rehearse reapplying previous known-good configuration.
6. Confirm database restore is not needed for app-only rollback.
7. If database state is involved, rehearse the restore decision path only against an isolated target.
8. Confirm `GET /health` succeeds after rollback rehearsal.
9. Confirm `GET /runtime/ready` returns `ok: true`.
10. Confirm `GET /runtime/config` returns safe configuration only.
11. Confirm `GET /runtime/observability` returns the contract.
12. Confirm protected routes require operator access.
13. Record rehearsal result and follow-up actions.

## Database rollback safety

Database rollback rehearsal must follow these rules:

- prefer forward-fix migration when safe;
- do not run destructive rollback on live production;
- do not restore over live production traffic;
- confirm fresh backup before any restore path;
- confirm backup checksum before restore path;
- confirm schema compatibility with selected image;
- record database decision as app-only rollback, config rollback, restore rehearsal, or forward fix.

## Verification checks

Required verification:

- candidate image identified;
- previous known-good image identified;
- previous known-good configuration identified;
- rollback decision owner identified;
- health route succeeds;
- readiness route is true;
- safe config route excludes secrets;
- observability contract is available;
- protected routes reject unauthenticated access;
- workflow gates remain enforced.

## Stop conditions

Stop the rehearsal if any of these occur:

- previous known-good image is unknown;
- previous known-good configuration is unknown;
- backup state is unknown when database state is involved;
- rollback owner is unavailable;
- protected route access is not enforced;
- workflow gate bypass is required;
- rehearsal target receives public production traffic;
- evidence capture would expose a secret value.

## Evidence capture

Record:

- rehearsal environment;
- candidate image tag or digest;
- previous known-good image tag or digest;
- previous known-good configuration source;
- database decision path;
- health result;
- readiness result;
- observability result;
- protected route result;
- stop condition result;
- follow-up owner.

Do not record secrets, connection strings, tokens, or private runtime values.

## Exit criteria

Rollback rehearsal is complete when:

- rollback path is understood;
- decision owner is recorded;
- health and readiness pass;
- protected routes remain protected;
- database decision path is recorded;
- follow-up actions are assigned;
- no guardrail was bypassed.

## Guardrails

- No public production launch.
- No destructive production rollback.
- No restore over live production traffic.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.

## Validation

Covered by:

```text
tests/integration/test_p9_step_03.py
```

The validation checks source references, preparation, decision points, execution, database safety, verification, stop conditions, evidence capture, exit criteria, and guardrails.
