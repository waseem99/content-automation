# P5 Step 02

This step adds API auth and operator identity for the operator API skeleton.

## Auth model

`OperatorAuthSettings` configures bearer-token access for protected routes.

Default behavior is fail-closed:

```python
create_app(database)
```

With no configured API keys, protected routes reject requests with `401`.

Test/runtime configuration can pass explicit keys:

```python
from src.operator_api.auth import OperatorAuthSettings

app = create_app(
    database,
    auth_settings=OperatorAuthSettings(api_keys={"token-value": "operator-id"}),
)
```

## Public route

- `GET /health`

The health route remains public and reports whether auth is required.

## Protected routes

All operator, demo, dashboard, approval, and audit routes require:

```text
Authorization: Bearer <token>
```

## Operator identity

Authenticated tokens resolve to `OperatorIdentity`.

The API uses the authenticated operator id for:

- workflow run actor;
- approval reviewer;
- demo approval reviewer;
- response envelope operator field where useful.

Caller-supplied reviewer fields are no longer trusted by API route handlers.

## Explicit local test mode

Tests can opt into disabled auth explicitly:

```python
OperatorAuthSettings.disabled_for_local_tests(operator_id="local-operator")
```

This is not the default path. It must be requested explicitly.

## Guardrails

- Health stays public.
- Protected routes fail closed without a valid token.
- Invalid tokens fail closed.
- Approval actions record authenticated operator identity.
- No publishing, scheduling, rendering, or external export is added.
- Existing P4 review gates remain authoritative.

## Validation

Covered by `tests/integration/test_p5_step_01.py` through the P1 Acceptance Harness P5 wildcard entry.
