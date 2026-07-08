# P7 Step 01

This step adds the first concrete runtime container package for the operator API.

Part of #105. Closes #106 after the PR merges.

## Goal

Provide a minimal package path that can start the existing P6 runtime entrypoint without changing API behavior.

## Files added or updated

```text
Dockerfile
.dockerignore
requirements.txt
docs/operations/p7-step-01.md
tests/integration/test_p7_step_01.py
.github/workflows/p1-acceptance-harness.yml
```

## Runtime entrypoint

The container command runs the existing runtime app:

```text
src.operator_api.entrypoint:app
```

The configured runtime factory remains:

```text
src.operator_api.entrypoint:create_runtime_app
```

## Build command

```bash
docker build -t content-automation-operator:local .
```

## Run command

```bash
docker run --rm -p 8000:8000 --env-file .env content-automation-operator:local
```

Runtime values stay outside the image and are supplied by the operator environment.

## Health check

The package health check uses the public health route:

```text
GET /health
```

Expected result:

- HTTP response succeeds;
- runtime process is reachable;
- response contains the existing health payload from the operator API.

## Package behavior

The container package:

- uses Python 3.11;
- installs dependencies from `requirements.txt`;
- starts the runtime with `uvicorn`;
- binds to `0.0.0.0:8000` inside the container;
- exposes port `8000`;
- runs as `appuser`;
- copies only runtime source and migrations needed by the existing app.

## Scope boundaries

- No API route changes are required.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No public production launch.

## Validation

Covered by:

```text
tests/integration/test_p7_step_01.py
```

The P1 Acceptance Harness includes:

```text
tests/integration/test_p7_step_*.py
```

The validation checks the package file, ignore file, runtime dependency, step documentation, and CI wildcard coverage.
