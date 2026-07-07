# P6 Step 02

This step documents service packaging guidance for the operator runtime.

No container image or service unit is added in this step. The goal is to define the packaging contract first.

## Runtime source

The runtime entrypoint added in P6-01 is:

```text
src.operator_api.entrypoint:app
```

The configured factory is:

```text
src.operator_api.entrypoint:create_runtime_app
```

## Local command

```bash
uvicorn src.operator_api.entrypoint:app --host 127.0.0.1 --port 8000
```

## Container packaging contract

A future container package should:

- use a Python runtime compatible with the CI version;
- install runtime dependencies from `requirements.txt`;
- set the working directory to the repository root;
- run the operator app through the P6 entrypoint;
- expose the configured API port;
- run the service as a non-root user where supported;
- leave runtime values outside the image;
- avoid baking private runtime values into layers;
- keep generated caches and build artifacts out of the final image.

## Service packaging contract

A future service definition should:

- start the app through the P6 entrypoint;
- set the working directory to the repository root;
- load runtime values from the deployment environment;
- restart only according to the host platform policy;
- send logs to stdout or the platform log collector;
- use the public health route for readiness checks.

## Required runtime values

The runtime expects values described in:

```text
.env.example
```

Database connection values continue to use the existing database settings.

Operator runtime values use the P5 runtime settings object.

## Healthcheck guidance

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

A package healthcheck should fail when the HTTP request fails or the response does not contain `ok: true`.

## Readiness guidance

Before marking an environment ready:

- migrations have been applied;
- health route responds;
- runtime config route responds in the intended environment;
- protected routes require operator access;
- the demo route can be exercised in a controlled internal environment.

## Non-goals

- No Dockerfile is added.
- No service unit is added.
- No deployment system is selected.
- No publishing is added.
- No scheduling is added.
- No rendering is added.
- No external export is added.

## Validation

Covered by:

```text
tests/integration/test_p6_step_02.py
```

The validation checks that the packaging contract, healthcheck guidance, readiness guidance, and non-goals remain documented.
