# P7 Step 02

This step documents and validates runtime health and readiness checks.

Part of #105. Closes #107 after the PR merges.

## Goal

Operators need two separate checks:

- liveness through the existing public health route;
- readiness through a runtime route that confirms the configured runtime can serve operator workflows.

## Liveness check

Use:

```text
GET /health
```

Expected healthy response fields:

- `ok`
- `service`
- `version`
- `database_configured`
- `auth_required`

The liveness check only confirms that the API process is reachable and returning its public health payload.

## Readiness check

Use:

```text
GET /runtime/ready
```

Expected ready response fields:

- `ok`
- `kind`
- `checks`
- `runtime`

Expected `kind` value:

```text
runtime_readiness
```

Expected `checks` fields:

- `runtime_configured`
- `database_configured`
- `database_reachable`
- `schema_required`
- `schema_ready`
- `migrations_ready`

## Readiness behavior

The readiness route returns HTTP 200 when:

- runtime settings are loaded;
- database is configured;
- database is reachable;
- schema is ready when schema readiness is required;
- expected migrations are applied when schema readiness is required.

The readiness route returns HTTP 503 when:

- database is not configured;
- database cannot be reached;
- schema readiness is required but the schema is not ready;
- expected migrations are missing.

## Runtime config check

Use:

```text
GET /runtime/config
```

The runtime config route remains a snapshot route. It does not replace readiness.

## Operator usage

Suggested local check order:

1. Start the runtime.
2. Call `GET /health`.
3. Call `GET /runtime/config`.
4. Call `GET /runtime/ready`.
5. Proceed with internal pilot actions only after readiness returns `ok: true`.

## Guardrails

- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No public production launch.
- No private runtime values are returned.

## Validation

Covered by:

```text
tests/integration/test_p7_step_02.py
```

The validation checks the public health route, runtime readiness route, ready and not-ready states, runtime config separation, and this operator note.
