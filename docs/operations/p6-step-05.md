# P6 Step 05

This step documents the end-to-end internal pilot runbook for the operator runtime.

The runbook is for controlled internal testing only.

## Goal

An operator should be able to:

- start the runtime;
- check health and runtime status;
- run the deterministic demo workflow;
- approve expected review gates;
- inspect the audit report;
- confirm the expected stop points.

## Prerequisites

Before starting the pilot:

- repository dependencies are installed;
- database settings are configured;
- migrations are applied;
- operator runtime values are configured from `.env.example`;
- operator access is configured for protected routes;
- P1 Acceptance Harness is green on the latest merged head.

## Step 1: Start runtime

Use the P6 runtime entrypoint:

```bash
uvicorn src.operator_api.entrypoint:app --host 127.0.0.1 --port 8000
```

Expected result:

- the service starts without import errors;
- logs show normal startup;
- no publishing, scheduling, rendering, or export action is started.

## Step 2: Check health

Call:

```text
GET /health
```

Expected result:

- `ok` is true;
- service name is present;
- version is present;
- database configured flag is present;
- access required flag is present.

## Step 3: Check runtime status

Call:

```text
GET /runtime/config
```

Expected result:

- `ok` is true;
- runtime host is present;
- runtime port is present;
- log level is present;
- demo mode flag is present;
- schema requirement flag is present;
- migrations directory is present;
- no sensitive values are returned.

## Step 4: Prepare workflow id

Create or select an internal workflow id for the pilot run.

Record:

- workflow id;
- operator id;
- pilot date;
- environment name;
- tester name.

## Step 5: Run demo scenario

Call:

```text
GET /demo/scenario
POST /demo/{workflow_run_id}/start
```

Expected result:

- scenario details are returned;
- expected stop points are visible;
- first run stops at `approve_packet`;
- queue shows a packet review item.

## Step 6: Approve packet gate

Call one of the supported pilot actions:

```text
POST /demo/{workflow_run_id}/approve-current
```

or use the explicit approval route from the queue card:

```text
POST /workflows/{workflow_run_id}/approvals
```

Expected result:

- action response has `ok: true`;
- status is approved;
- reviewed by value matches the operator identity;
- workflow does not skip the next review gate.

## Step 7: Approve output gate

Resume the workflow before approving the output gate.

Call:

```text
POST /demo/{workflow_run_id}/start
GET /demo/{workflow_run_id}/status
POST /demo/{workflow_run_id}/approve-current
```

Expected result:

- workflow stops at `approve_output` before approval;
- approval records the operator identity;
- next run reaches the step-plan stop point.

## Step 8: Confirm final stop point

Call:

```text
POST /demo/{workflow_run_id}/start
GET /demo/{workflow_run_id}/status
```

Expected result:

- next action is `continue_p3_delivery`;
- pilot stops there;
- no delivery, publishing, scheduling, rendering, or export action is triggered.

## Step 9: Inspect audit report

Call:

```text
GET /workflows/{workflow_run_id}/audit
```

Expected result:

- workflow summary is present;
- status summary is present;
- event timeline is present;
- reviews are present;
- queue state is present;
- packages and manifests are present as applicable;
- packet and output approvals show the operator identity.

## Step 10: Record pilot result

Record:

- workflow id;
- operator id;
- completed gates;
- final stop point;
- audit report status;
- any failed request;
- any follow-on issue.

## Pass criteria

The pilot passes when:

- health route succeeds;
- runtime config route succeeds;
- demo scenario starts;
- packet gate is approved explicitly;
- output gate is approved explicitly;
- final stop point is `continue_p3_delivery`;
- audit report includes the expected review and timeline data;
- no protected route works without configured access;
- no non-goal action is triggered.

## Fail criteria

The pilot fails when:

- runtime cannot start;
- health route fails;
- runtime config route fails;
- demo scenario cannot start;
- approval does not record operator identity;
- workflow skips a review gate;
- audit report is missing required sections;
- any non-goal action is triggered.

## Guardrails

- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No public production launch.

## Validation

Covered by:

```text
tests/integration/test_p6_step_05.py
```

The validation checks that the runbook documents startup, health, runtime status, demo workflow, approvals, audit inspection, stop points, pass/fail criteria, and guardrails.
