# PostgreSQL Development Foundation

## Design decision

The Phase 1 foundation uses **psycopg 3 with explicit SQL repositories** rather than an ORM. This keeps the database contract visible, supports PostgreSQL-native JSONB and arrays, and avoids coupling domain services to persistence models.

All multi-record service operations must execute through `unit_of_work(database)` so success commits atomically and exceptions roll back the full operation.

## Local database

```bash
docker compose -f docker-compose.postgres.yml up -d
```

Set the development connection in `.env` using credentials configured for your local machine:

```dotenv
DATABASE_URL=
DATABASE_POOL_MIN_SIZE=1
DATABASE_POOL_MAX_SIZE=10
DATABASE_POOL_TIMEOUT_SEC=15
DATABASE_CONNECT_TIMEOUT_SEC=10
DATABASE_STATEMENT_TIMEOUT_MS=60000
DATABASE_APPLICATION_NAME=football-brief-dev
DATABASE_MIGRATIONS_DIR=migrations
DATABASE_REQUIRE_SCHEMA=true
```

Never reuse local development credentials in shared or production environments.

## Commands

Apply pending migrations:

```bash
python -m src.infrastructure.database.cli migrate
```

Inspect migration checksums:

```bash
python -m src.infrastructure.database.cli status
```

Check readiness:

```bash
python -m src.infrastructure.database.cli health
python -m src.infrastructure.database.cli health --json
```

## Migration behavior

- Migrations are discovered by numeric filename.
- File bytes are SHA-256 hashed.
- Applied filename and checksum are recorded in `football_brief.schema_migrations`.
- Editing an applied migration produces a checksum failure.
- The runner strips only the outer `BEGIN`/`COMMIT` wrapper and executes the SQL body plus history insert in one driver-managed transaction.
- Failed migrations are rolled back and are not recorded as applied.
- Production corrections use new forward-only migrations.

## Integration tests

Use a dedicated disposable database. The suite drops the `football_brief` schema before and after the run.

```bash
createdb football_brief_test
pytest -m integration tests/integration/test_database_foundation.py
```

Configure `FOOTBALL_BRIEF_TEST_DATABASE_URL` for that disposable database before running the test command. Never point it at a shared, staging, or production database.

## Service usage

```python
from src.infrastructure.database import Database, get_database_settings
from src.infrastructure.database.uow import unit_of_work

settings = get_database_settings()
database = Database(settings)
database.open()

try:
    with unit_of_work(database) as uow:
        item = uow.content_items.create(...)
        workflow = uow.workflow_runs.create(...)
finally:
    database.close()
```

## Security rules

- Database URLs are represented as `SecretStr` and must not be logged.
- SQL values are passed as parameters; do not interpolate user values into SQL.
- Store provider secrets in a secret manager in production.
- Store large media in object storage, not PostgreSQL.
- Store only storage references, metadata, hashes, rights evidence references, and audit records in PostgreSQL.
- Restrict the application role to the required schema and operations.
