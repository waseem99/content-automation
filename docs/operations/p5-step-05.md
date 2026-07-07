# P5 Step 05

This step defines the minimum operator UI contract before any frontend framework is added.

## Purpose

The UI should consume the existing P5 routes and response shapes. This step is documentation only.

## Screens

### Queue screen

Purpose: show current workflow items that need operator attention.

Routes:

- `GET /workflows/{workflow_run_id}/queue`
- `GET /workflows/{workflow_run_id}/dashboard/queue`

Required fields:

- workflow id
- operator id
- item count
- card id
- item type
- status
- title
- subtitle
- created time
- actions

### Review detail screen

Purpose: show one review item with timeline context.

Routes:

- `GET /workflows/{workflow_run_id}/dashboard/queue`
- `GET /workflows/{workflow_run_id}/audit`

Required fields:

- workflow id
- resource id
- item type
- status
- title
- metadata
- timeline context
- action name

### Approval action flow

Purpose: submit one explicit operator action.

Route:

- `POST /workflows/{workflow_run_id}/approvals`

Request fields:

- action
- resource id
- optional rationale

Response fields:

- ok
- kind
- action
- workflow id
- resource id
- status
- reviewed by
- result or error

### Demo run screen

Purpose: run the deterministic demo scenario.

Routes:

- `GET /demo/scenario`
- `POST /demo/{workflow_run_id}/start`
- `POST /demo/{workflow_run_id}/approve-current`
- `GET /demo/{workflow_run_id}/status`

Required fields:

- scenario id
- title
- topic
- expected stop points
- next action
- queue cards
- operator id

### Workflow audit screen

Purpose: show the read-only workflow report.

Route:

- `GET /workflows/{workflow_run_id}/audit`

Required sections:

- workflow summary
- status summary
- event timeline
- stage executions
- reviews
- queue cards
- packages
- manifests

### Runtime status screen

Purpose: show safe runtime metadata.

Routes:

- `GET /health`
- `GET /runtime/config`

Required fields:

- service name
- version
- database configured
- access required
- host
- port
- log level
- demo mode
- schema requirement
- migrations directory

## Route map

| Route | Screen |
|---|---|
| `GET /health` | Runtime status screen |
| `GET /runtime/config` | Runtime status screen |
| `GET /workflows/{workflow_run_id}/queue` | Queue screen |
| `GET /workflows/{workflow_run_id}/dashboard/queue` | Queue screen, review detail screen |
| `GET /workflows/{workflow_run_id}/dashboard/schema` | UI bootstrap |
| `POST /workflows/{workflow_run_id}/approvals` | Approval action flow |
| `GET /workflows/{workflow_run_id}/audit` | Review detail screen, workflow audit screen |
| `GET /demo/scenario` | Demo run screen |
| `POST /demo/{workflow_run_id}/start` | Demo run screen |
| `POST /demo/{workflow_run_id}/approve-current` | Demo run screen |
| `GET /demo/{workflow_run_id}/status` | Demo run screen |

## Guardrails

- No frontend framework is added.
- No new API route is added.
- No publishing is added.
- No scheduling is added.
- No rendering is added.
- No external export is added.

## Validation

Covered by `tests/integration/test_p5_step_05.py`.
