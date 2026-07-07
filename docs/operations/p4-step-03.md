# P4 Step 03

This step defines stable response shapes for a future operator dashboard.

## Service

`P4DashboardContracts` adapts `P4OperatorSurface` responses into UI-ready shapes.

It remains a backend contract layer only. It does not add a frontend, web server, publishing, rendering, scheduling, or external export.

## Queue card shape

```json
{
  "card_id": "packet_review:<id>",
  "resource_id": "<id>",
  "workflow_run_id": "<workflow-id>",
  "item_type": "packet_review",
  "status": "pending",
  "title": "Derby preview",
  "subtitle": "Research packet review required",
  "created_at": "<iso timestamp>",
  "actions": [
    {"name": "approve_packet", "resource_id": "<id>", "enabled": true}
  ],
  "metadata": {}
}
```

## Review detail shape

```json
{
  "ok": true,
  "kind": "review_detail",
  "workflow_run_id": "<workflow-id>",
  "resource_id": "<id>",
  "item_type": "packet_review",
  "card": {},
  "actions": [],
  "metadata": {}
}
```

## Approval action shape

```json
{
  "ok": true,
  "kind": "approval_action",
  "action": "approve_packet",
  "workflow_run_id": "<workflow-id>",
  "resource_id": "<id>",
  "status": "approved",
  "reviewed_by": "operator",
  "result": {}
}
```

## Package view shape

```json
{
  "ok": true,
  "kind": "package_view",
  "workflow_run_id": "<workflow-id>",
  "package_id": "<package-id>",
  "status": "approved",
  "package": {}
}
```

## Manifest view shape

```json
{
  "ok": true,
  "kind": "manifest_view",
  "workflow_run_id": "<workflow-id>",
  "package_id": "<package-id>",
  "items": [],
  "count": 0
}
```

## Blocked state shape

```json
{
  "ok": true,
  "kind": "blocked_state",
  "workflow_run_id": "<workflow-id>",
  "status": "waiting",
  "is_blocked": true,
  "next_action": "approve_packet",
  "current_step": {},
  "steps": []
}
```

## Error shape

```json
{
  "ok": false,
  "kind": "package_view",
  "error": "package was not found for workflow"
}
```

## Guardrails

- Contracts map to existing P4 surface and operator services.
- Approval actions remain explicit.
- Unsupported actions fail closed.
- Wrong-workflow resources fail closed.
- P2/P3 operator tools remain compatible.

## Validation

Covered by `tests/integration/test_p4_step_03.py` through the P1 Acceptance Harness P4 wildcard entry.
