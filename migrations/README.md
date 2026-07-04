# Database Migrations

These migrations establish the Phase 0 and Phase 1 platform foundation for Football Brief.

## Target

- PostgreSQL 15+
- A database role allowed to create the `football_brief` schema
- Permission to enable the `pgcrypto` extension for `gen_random_uuid()`

## Order

1. `0001_phase0_asset_rights.sql`
2. `0002_phase1_workflow_foundation.sql`

Migrations are applied only in numeric filename order.

## Local execution

Configure `DATABASE_URL`, then run the application migration command:

```bash
python -m src.infrastructure.database.cli migrate
```

The runner:

1. Discovers numbered SQL files.
2. Hashes the exact file bytes with SHA-256.
3. Executes each pending migration atomically.
4. Records filename and checksum in `football_brief.schema_migrations`.
5. Rejects an applied migration whose file checksum later changes.

Do not apply these migrations manually with `psql` in a managed environment because doing so bypasses migration history and checksum enforcement.

## Verification

```bash
python -m src.infrastructure.database.cli status
python -m src.infrastructure.database.cli health
pytest -m acceptance tests/acceptance/test_migration_contracts.py
```

For a live PostgreSQL integration run:

```bash
export FOOTBALL_BRIEF_TEST_DATABASE_URL=postgresql://localhost/football_brief_test
pytest -m integration tests/integration/test_database_foundation.py
```

The test database must be disposable because the fixture drops and recreates the `football_brief` schema.

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
