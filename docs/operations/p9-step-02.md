# P9 Step 02

This step documents a restore rehearsal that proves backup usability without risking live production traffic.

Part of #131. Closes #133 after the PR merges.

## Goal

Prove that a database backup can be restored into an isolated target environment and verified against runtime expectations before production rollout.

## Source references

This runbook builds on:

```text
docs/operations/p8-step-03.md
docs/operations/p9-step-01.md
```

## Rehearsal scope

The restore rehearsal covers:

- selecting a backup candidate;
- verifying backup metadata and checksum;
- preparing an isolated restore target;
- restoring into the isolated target;
- verifying migration status;
- verifying runtime health and readiness against the restored target;
- confirming protected routes remain protected;
- recording rehearsal evidence.

The rehearsal must not restore over live production traffic.

## Participants

Recommended participants:

- database operator;
- deployment operator;
- reviewer for evidence;
- decision owner for rehearsal result.

## Isolation requirements

The restore target must be:

- separate from production database;
- separate from staging database when staging is actively used;
- network-restricted;
- accessible only to rehearsal operators;
- configured with safe non-public runtime access;
- disposable after evidence is captured.

## Preparation checklist

Before restore rehearsal:

1. Confirm target environment is isolated.
2. Confirm restore source backup name.
3. Confirm backup created time.
4. Confirm backup checksum.
5. Confirm backup environment label.
6. Confirm a rollback owner is available.
7. Confirm application image compatibility with restored schema.
8. Confirm no production traffic points to the restore target.
9. Confirm secrets are injected outside git.
10. Confirm restore target can be destroyed after rehearsal.

## Restore execution

Recommended command shape:

```bash
pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DATABASE_URL" backup.dump
```

Execution steps:

1. Create or select the isolated restore target.
2. Inject restore target `DATABASE_URL` outside git.
3. Run the restore command against the isolated target.
4. Run database health check.
5. Run migration status check.
6. Start the runtime against the isolated target.
7. Confirm `GET /health` succeeds.
8. Confirm `GET /runtime/ready` returns `ok: true`.
9. Confirm `GET /runtime/config` returns safe configuration only.
10. Confirm protected routes require operator access.
11. Record evidence and destroy the restore target when no longer needed.

## Verification checks

Required verification:

- backup checksum is recorded;
- database health check passes;
- migration status matches expectations;
- runtime health route responds;
- runtime readiness route is true;
- safe configuration snapshot excludes secrets;
- queue route can read expected restored data;
- audit route can read expected restored data;
- protected routes reject unauthenticated access;
- rehearsal notes contain no secret values.

## Stop conditions

Stop the rehearsal if any of these occur:

- restore target is not isolated;
- backup checksum is missing or mismatched;
- restore command fails;
- migration status is unexpected;
- runtime readiness fails;
- protected route access is not enforced;
- restored target receives live production traffic;
- evidence capture would expose a secret value.

## Evidence capture

Record:

- restore target name;
- backup file name;
- backup created time;
- checksum verification result;
- restore command result;
- migration status result;
- runtime health result;
- runtime readiness result;
- queue route verification result;
- audit route verification result;
- protected route verification result;
- destroy or retention decision.

Do not record passwords, tokens, connection strings, or private runtime values.

## Guardrails

- No restore over live production traffic.
- No shared production restore target.
- No secret values in evidence.
- No private runtime values in notes.
- No public production launch.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.

## Validation

Covered by:

```text
tests/integration/test_p9_step_02.py
```

The validation checks source references, isolation, preparation, restore execution, verification, stop conditions, evidence capture, and guardrails.
