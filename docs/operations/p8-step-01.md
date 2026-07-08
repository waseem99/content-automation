# P8 Step 01

This step defines the production service shape for the operator runtime.

Part of #118. Closes #119 after the PR merges.

## Goal

Define a provider-neutral service definition for controlled production deployment without choosing a cloud platform, orchestrator, or managed runtime.

## Service identity

Recommended service name:

```text
content-automation-operator-api
```

Service role:

- serve operator API routes;
- expose liveness, readiness, runtime config, and observability contract routes;
- support controlled internal operator workflows;
- preserve all workflow gate guardrails.

## Runtime image

The service uses the existing runtime package path:

```text
Dockerfile
.dockerignore
```

Build command:

```bash
docker build -t content-automation-operator:local .
```

## Runtime command

The runtime command remains:

```text
uvicorn src.operator_api.entrypoint:app --host 0.0.0.0 --port 8000
```

Entrypoint:

```text
src.operator_api.entrypoint:app
```

Runtime factory:

```text
src.operator_api.entrypoint:create_runtime_app
```

## Port contract

Container port:

```text
8000
```

External exposure should be private/internal by default.

Public internet exposure is out of scope for this phase.

## Process model

Recommended process model:

- one web process per container;
- horizontal scale by adding runtime instances;
- no in-process scheduler;
- no background publishing worker;
- no renderer process;
- no external export process.

## Dependencies

Required runtime dependencies:

- PostgreSQL database reachable through `DATABASE_URL`;
- applied migrations in `migrations`;
- operator access configuration for protected routes;
- runtime environment variables supplied outside the image.

## Health and readiness checks

Liveness:

```text
GET /health
```

Configuration snapshot:

```text
GET /runtime/config
```

Readiness:

```text
GET /runtime/ready
```

Observability contract:

```text
GET /runtime/observability
```

Readiness must pass before internal operator workflow actions begin.

## Restart policy

Recommended restart behavior:

- restart failed runtime process;
- do not restart repeatedly without surfacing an alert;
- readiness failure should remove the instance from serving traffic;
- liveness failure should restart the instance.

## Deployment boundaries

This step does not choose:

- AWS ECS;
- Kubernetes;
- VM systemd;
- serverless platform;
- managed container platform;
- dashboard or metrics vendor.

## Guardrails

- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.
- No public production launch.
- No private runtime values.

## Validation

Covered by:

```text
tests/integration/test_p8_step_01.py
```

The P1 Acceptance Harness includes:

```text
tests/integration/test_p8_step_*.py
```

The validation checks service identity, runtime command, port contract, process model, dependencies, health and readiness checks, deployment boundaries, guardrails, and CI wildcard coverage.
