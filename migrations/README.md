# Database Migrations

These migrations establish the Phase 0 and Phase 1 platform foundation for Football Brief.

## Target

- PostgreSQL 15+
- A database role allowed to create the `football_brief` schema
- The `pgcrypto` extension for `gen_random_uuid()`

## Order

1. `0001_phase0_asset_rights.sql`
2. `0002_phase1_workflow_foundation.sql`

Apply migrations only in numeric order.

## Local execution

```bash
createdb football_brief_dev
psql football_brief_dev -v ON_ERROR_STOP=1 -f migrations/0001_phase0_asset_rights.sql
psql football_brief_dev -v ON_ERROR_STOP=1 -f migrations/0002_phase1_workflow_foundation.sql
```

## Verification

```bash
psql football_brief_dev -c "\dt football_brief.*"
pytest -m acceptance tests/acceptance/test_migration_contracts.py
```

The acceptance suite should later include a PostgreSQL integration job that:

1. Starts an empty PostgreSQL database.
2. Applies every migration with `ON_ERROR_STOP=1`.
3. Runs constraint and transaction tests.
4. Applies representative seed data.
5. Verifies publish-mode blocking behavior through the application service layer.

## Migration policy

- Never modify an already deployed migration.
- Add a new numbered migration for every schema change.
- Migrations must run inside a transaction unless PostgreSQL prohibits the operation.
- Destructive changes require a data migration, rollback plan, and backup verification.
- Store media in object storage; store only references and hashes in PostgreSQL.
- Do not store provider secrets or raw confidential payloads.
- Treat approval, workflow-event, provider-call, cost, and manifest records as audit evidence.

## Rollback

These foundation migrations intentionally do not include automated `DROP TABLE` rollback sections because destructive rollback can erase audit and rights evidence.

For pre-production environments, recreate the database when necessary. For production, use forward-only corrective migrations and restore from a verified backup when a full rollback is required.

## Service-layer rules not fully enforceable in SQL

The application must additionally verify:

- An approved rights record has at least one relevant evidence record.
- The requested platform and territory are covered.
- The licence is active at render and publication time.
- The requested operation is allowed: editorial, commercial, modification, or synthetic edit.
- Asset bytes match the stored hash.
- Publish manifests are immutable after approval.
- Workflow and stage cost totals reconcile with cost entries.
- Only approved voices, fonts, music, and visual assets enter publish manifests.
