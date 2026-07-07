# P5 Step 02

This step adds API key access and operator identity for the operator API skeleton.

## Access model

`OperatorAuthSettings` configures internal operator keys for protected routes.

Default behavior is fail-closed:

```python
create_app(database)
```

With no configured keys, protected routes reject requests with `401`.

Test/runtime configuration can pass explicit keys:

```python
from src.operator_api.auth import OperatorAuthSettings

app = create_app(
    database,
    auth_settings=OperatorAuthSettings(api_keys={"key-value": "operator-id"}),
)
```

## Public route

- `GET /health`

The health route remains public and reports whether protected access is required.

## Protected routes

All operator, demo, dashboard, approval, and audit routes require the internal header:

```text
X-Operator-Key: <key>
```

## Operator identity

Valid keys resolve to `OperatorIdentity`.

The API uses the authenticated operator id for:

- workflow run actor;
- approval reviewer;
- demo approval reviewer;
- response envelope operator field where useful.

Caller-supplied reviewer fields are no longer trusted by API route handlers.

## Explicit local test mode

Tests can opt into disabled access checks explicitly:

```python
OperatorAuthSettings.disabled_for_local_tests(operator_id="local-operator")
```

This is not the default path. It must be requested explicitly.

## Guardrails

- Health stays public.
- Protected routes fail closed without a valid key.
- Invalid keys fail closed.
- Approval actions record authenticated operator identity.
- No publishing, scheduling, rendering, or external export is added.
- Existing P4 review gates remain authoritative.

## Validation

Covered by `tests/integration/test_p5_step_01.py` through the P1 Acceptance Harness P5 wildcard entry.
