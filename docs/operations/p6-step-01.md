# P6 Step 01

This step adds a runtime entrypoint and local start command metadata for the operator API.

## Runtime module

```text
src/operator_api/entrypoint.py
```

## Exports

- `app`
- `create_runtime_app()`
- `runtime_start_command(settings=None)`
- `runtime_metadata(settings=None)`

## App import path

```text
src.operator_api.entrypoint:app
```

## Factory import path

```text
src.operator_api.entrypoint:create_runtime_app
```

## Suggested local command

```bash
uvicorn src.operator_api.entrypoint:app --host 127.0.0.1 --port 8000
```

The command uses the existing P5 configured app stack and runtime settings.

## Safe defaults

- localhost host value
- port 8000
- protected route access remains enabled by default
- runtime metadata excludes sensitive values
- health route remains public

## Validation

Covered by:

```text
tests/integration/test_p6_step_01.py
```

The test validates that the app is importable, health works through the test client, command metadata uses runtime settings, and the metadata snapshot stays safe and complete.
