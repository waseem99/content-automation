# P4 Step 02

This step adds a service-contract layer for operator-facing workflow and review operations.

## Service

`P4OperatorSurface` is intentionally a service layer, not a web framework adapter. Future HTTP/API handlers can call it directly and keep routing thin.

## Contract envelope

Every method returns a JSON-friendly envelope:

```json
{
  "ok": true,
  "kind": "queue"
}
```

On fail-closed errors:

```json
{
  "ok": false,
  "kind": "approve_package",
  "error": "package was not found for workflow"
}
```

## Available contracts

Workflow and intake:

- `create_intake`
- `run_workflow`
- `queue`

Approval actions:

- `approve_packet`
- `approve_output`
- `request_option`
- `approve_option`
- `request_package`
- `approve_package`

Status views:

- `package_status`
- `manifest_status`

## Guardrails

- The surface reuses existing P4 control and operator services.
- It does not duplicate business rules.
- Invalid workflow/resource combinations return `ok: false`.
- Approval actions remain explicit.
- No publishing, scheduling, rendering, or external export is performed.

## Validation

Covered by `tests/integration/test_p4_step_02.py` through the P1 Acceptance Harness P4 wildcard entry.
