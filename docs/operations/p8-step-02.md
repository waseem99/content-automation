# P8 Step 02

This step defines staging and production environment configuration expectations.

Part of #118. Closes #120 after the PR merges.

## Goal

Keep production configuration explicit, safe to review, and separated from secrets before controlled deployment work begins.

## Files

```text
.env.example
.env.production.example
docs/operations/p8-step-02.md
tests/integration/test_p8_step_02.py
```

## Environment tiers

Recommended tiers:

- local development;
- staging;
- production.

Staging should mirror production settings where possible, but use separate database, secrets, and operator access values.

Production should use managed secret injection and should not rely on checked-in secret values.

## Required runtime settings

Database settings:

- `DATABASE_URL`
- `DATABASE_POOL_MIN_SIZE`
- `DATABASE_POOL_MAX_SIZE`
- `DATABASE_POOL_TIMEOUT_SEC`
- `DATABASE_CONNECT_TIMEOUT_SEC`
- `DATABASE_STATEMENT_TIMEOUT_MS`
- `DATABASE_APPLICATION_NAME`
- `DATABASE_MIGRATIONS_DIR`
- `DATABASE_REQUIRE_SCHEMA`

Operator runtime settings:

- `OPERATOR_RUNTIME_API_HOST`
- `OPERATOR_RUNTIME_API_PORT`
- `OPERATOR_RUNTIME_LOG_LEVEL`
- `OPERATOR_RUNTIME_DEMO_MODE`
- `OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA`
- `OPERATOR_RUNTIME_DATABASE_MIGRATIONS_DIR`

Provider settings:

- `OPENAI_MODEL`
- `ELEVENLABS_MODEL`
- `WHISPER_MODEL`
- `WHISPER_DEVICE`
- `OPENAI_IMAGE_MODEL`
- `OPENAI_IMAGE_SIZE`
- `OPENAI_IMAGE_QUALITY`

## Required secrets

Secrets must be supplied by the deployment environment or secret manager:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `SERPAPI_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- operator access value for protected routes.

Checked-in files must not contain real secret values.

## Safe production example

Use:

```text
.env.production.example
```

The production example may include safe defaults such as ports, model names, log level, migration directory, and schema requirement.

The production example must not include real tokens, passwords, API keys, or private runtime values.

## Deployment injection rules

- Non-secret values may be reviewed in repository docs.
- Secrets must be injected at deploy time.
- Staging and production must not share the same database.
- Staging and production must not share the same operator access value.
- Runtime config routes must not return secret values.

## Pre-deploy checks

Before deployment:

1. Confirm `DATABASE_REQUIRE_SCHEMA=true`.
2. Confirm `OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA=true`.
3. Confirm migrations are applied.
4. Confirm `GET /health` succeeds.
5. Confirm `GET /runtime/config` returns safe public configuration only.
6. Confirm `GET /runtime/ready` returns `ok: true`.
7. Confirm protected routes require operator access.
8. Confirm `GET /runtime/observability` returns the contract.

## Guardrails

- No secret values in git.
- No shared staging and production secrets.
- No private runtime values in public snapshots.
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
tests/integration/test_p8_step_02.py
```

The validation checks required variables, secret separation, safe production example values, deployment injection rules, pre-deploy checks, and guardrails.
