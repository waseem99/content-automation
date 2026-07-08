# P7 Step 04

This step defines the static operator UI API wiring contract.

Part of #105. Closes #109 after the PR merges.

## Goal

Document how the existing static shell maps to operator API routes before adding any frontend framework, build step, or client-side business logic.

## Static shell files

```text
src/operator_ui/static/index.html
src/operator_ui/static/styles.css
```

## Runtime status wiring

Screen: `runtime-status`

Routes:

```text
GET /health
GET /runtime/config
GET /runtime/ready
GET /runtime/observability
```

Expected fields:

- service
- version
- database configured
- access required
- runtime config
- readiness checks
- observability contract

Empty state:

- show waiting state until a route response is available.

Error state:

- show route name, status code, and safe error summary.
- do not show private runtime values.

## Queue wiring

Screen: `queue`

Routes:

```text
GET /workflows/{workflow_run_id}/queue
GET /workflows/{workflow_run_id}/dashboard/queue
```

Expected fields:

- workflow id
- operator id
- item count
- card id
- resource id
- item type
- status
- actions

Empty state:

- show no review items when count is zero.

Error state:

- show route name, status code, and safe error summary.
- keep approval buttons disabled when queue data fails.

## Demo run wiring

Screen: `demo-run`

Routes:

```text
GET /demo/scenario
POST /demo/{workflow_run_id}/start
POST /demo/{workflow_run_id}/approve-current
GET /demo/{workflow_run_id}/status
```

Expected fields:

- scenario id
- topic
- expected stop points
- next action
- operator id

Empty state:

- show that no scenario has been loaded yet.

Error state:

- show route name, status code, and safe error summary.
- do not auto-approve any review gate after an error.

## Audit report wiring

Screen: `audit-report`

Route:

```text
GET /workflows/{workflow_run_id}/audit
```

Expected sections:

- workflow summary
- status summary
- event timeline
- stage executions
- reviews
- queue cards
- packages
- manifests

Empty state:

- show no audit report loaded until a workflow id is supplied.

Error state:

- show route name, status code, and safe error summary.

## Operator access behavior

Protected routes require the operator access header configured by the API.

The UI contract must handle HTTP 401 by showing that operator access is required without exposing the configured access value.

## Guardrails

- No frontend framework is added.
- No build step is added.
- No hidden business logic is added.
- No publishing action is present.
- No scheduling action is present.
- No rendering action is present.
- No external export action is present.
- No workflow gate is bypassed.
- No private runtime values are displayed.

## Validation

Covered by:

```text
tests/integration/test_p7_step_04.py
```

The validation checks route wiring, screen mapping, expected fields, empty states, error states, operator access behavior, and guardrails.
