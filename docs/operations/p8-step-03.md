# P8 Step 03

This step documents database backup and restore expectations for controlled production operation.

Part of #118. Closes #121 after the PR merges.

## Goal

Give operators a provider-neutral runbook for backing up, restoring, and verifying the PostgreSQL database before and after controlled deployment activity.

## Scope

This runbook covers:

- backup preparation;
- backup creation;
- backup storage expectations;
- restore preparation;
- restore execution;
- restore verification;
- guardrails.

This runbook does not select a cloud backup product or managed database vendor.

## Backup triggers

Create or confirm a backup before:

- production deployment;
- database migration;
- configuration change that affects database connectivity;
- rollback rehearsal;
- restore rehearsal;
- incident response activity.

## Backup preparation

Before creating a backup:

1. Confirm the target environment.
2. Confirm the database name and connection target.
3. Confirm migrations are applied.
4. Confirm `GET /runtime/ready` returns `ok: true`.
5. Confirm no deployment is actively changing schema.
6. Confirm backup destination is encrypted.
7. Confirm backup access is limited to operators who need it.

## Backup command shape

Recommended logical backup shape:

```bash
pg_dump --format=custom --no-owner --no-acl --file backup.dump "$DATABASE_URL"
```

The final command may vary by provider, but it must preserve schema and data needed by the operator runtime.

## Backup naming

Recommended naming pattern:

```text
content-automation-operator-ENVIRONMENT-YYYYMMDD-HHMMSS.dump
```

Example:

```text
content-automation-operator-production-20260708-060000.dump
```

## Backup storage expectations

Backups should be:

- encrypted at rest;
- access controlled;
- retained according to policy;
- stored outside the running application container;
- verified with metadata such as created time, environment, database name, and checksum.

## Restore preparation

Before restore:

1. Confirm restore target environment.
2. Confirm restore source backup.
3. Confirm backup checksum.
4. Confirm migration version expected after restore.
5. Confirm rollback window and decision owner.
6. Confirm application traffic is paused or isolated.
7. Confirm current database state has a fresh backup.

## Restore command shape

Recommended logical restore shape:

```bash
pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DATABASE_URL" backup.dump
```

The final command may vary by provider, but it must restore schema and data required by the runtime.

## Restore verification

After restore:

1. Run database health check.
2. Run migration status check.
3. Confirm `GET /health` succeeds.
4. Confirm `GET /runtime/config` returns safe configuration only.
5. Confirm `GET /runtime/ready` returns `ok: true`.
6. Confirm protected routes still require operator access.
7. Confirm audit and queue routes can read expected restored data.
8. Record restore result and any follow-up action.

## Rehearsal cadence

Recommended rehearsal cadence:

- perform restore rehearsal before first production deployment;
- repeat after migration changes;
- repeat after major backup policy changes;
- record rehearsal result in operator notes.

## Guardrails

- No restore without confirming target environment.
- No restore without a fresh current-state backup.
- No production restore rehearsal against live production traffic.
- No backup stored inside the application container.
- No secret values in logs.
- No private runtime values in backup notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.

## Validation

Covered by:

```text
tests/integration/test_p8_step_03.py
```

The validation checks backup triggers, backup preparation, backup command shape, storage expectations, restore preparation, restore command shape, restore verification, rehearsal cadence, and guardrails.
