# P5 Step 03

This step adds runtime settings for the P5 operator API.

## Files

- `src/operator_api/runtime_config.py`
- `src/operator_api/runtime_factory.py`
- `.env.example`
- `tests/integration/test_p5_step_03.py`

## Settings covered

- API host
- API port
- log level
- demo mode flag
- database schema requirement
- migrations directory

The existing database settings module continues to own database connection details.

## Configured app

`create_configured_app(...)` wraps the existing operator API app and attaches runtime settings without changing the P5 route contracts.

It adds:

```text
GET /runtime/config
```

The route returns a safe public snapshot and does not expose sensitive values.

## Defaults

- Host: localhost
- Port: 8000
- Log level: INFO
- Demo mode: off
- Schema required: yes
- Migrations directory: `migrations`

## Guardrails

- No publishing.
- No scheduling.
- No rendering.
- No external export.
- Existing P4/P5 review controls remain authoritative.

## Validation

The tests cover defaults, environment overrides, database setting projection, and configured app snapshot output.
