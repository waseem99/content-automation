# P5 Step 01

This step adds a thin HTTP API skeleton over the completed P4 services.

## Package

`src.operator_api`

The app is created through:

```python
from src.operator_api import create_app

app = create_app(database)
```

The app can also be imported without a database for health checks:

```python
app = create_app()
```

## Routes

Health:

- `GET /health`

Workflow and queue:

- `POST /workflows/{workflow_run_id}/run`
- `GET /workflows/{workflow_run_id}/queue`
- `POST /workflows/{workflow_run_id}/approvals`

Dashboard:

- `GET /workflows/{workflow_run_id}/dashboard/queue`
- `GET /workflows/{workflow_run_id}/dashboard/schema`

Demo:

- `GET /demo/scenario`
- `POST /demo/{workflow_run_id}/start`
- `POST /demo/{workflow_run_id}/approve-current`
- `GET /demo/{workflow_run_id}/status`

Audit:

- `GET /workflows/{workflow_run_id}/audit`

## Service mapping

- `P4OperatorSurface` powers workflow, queue, and approval routes.
- `P4DashboardContracts` powers dashboard routes.
- `P4DemoFlowService` powers demo routes.
- `P4AuditReportService` powers audit routes.

## Guardrails

- The API layer is thin and does not duplicate business logic.
- Auth is not included in this step; P5-02 will add auth and operator identity.
- No publishing, scheduling, rendering, or external export is added.
- Existing P4 review gates remain authoritative.
- The app is importable without starting a server.

## Validation

Covered by `tests/integration/test_p5_step_01.py` through the P1 Acceptance Harness P5 wildcard entry.
