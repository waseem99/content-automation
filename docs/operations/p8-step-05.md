# P8 Step 05

This step maps the P7 observability contract into operational dashboard and alert expectations.

Part of #118. Closes #123 after the PR merges.

## Goal

Define provider-neutral dashboard and alert expectations using the existing runtime observability contract.

## Source contract

Runtime contract route:

```text
GET /runtime/observability
```

Source implementation:

```text
src/operator_api/observability.py
```

The dashboard plan must stay aligned with the P7 event fields, metric names, bounded labels, and telemetry guardrails.

## Required dashboard panels

### Service health

Purpose:

- show whether the runtime process is reachable;
- show liveness failures;
- show runtime startup trends.

Signals:

- `runtime_startup_total`
- `runtime_healthcheck_total`
- `runtime_readiness_total`

Related routes:

```text
GET /health
GET /runtime/ready
```

### Readiness and migration state

Purpose:

- show readiness status;
- show database reachability;
- show schema and migration readiness.

Fields:

- database configured;
- database reachable;
- schema required;
- schema ready;
- migrations ready.

Related route:

```text
GET /runtime/ready
```

### API request volume and latency

Purpose:

- show route traffic;
- show request duration;
- show status code family trends.

Signals:

- `api_request_total`
- `api_request_duration_ms`

Labels:

- `route_name`
- `status_family`
- `outcome`

### Workflow and operator actions

Purpose:

- show workflow action volume;
- show operator approval activity;
- show action outcomes.

Signals:

- `workflow_action_total`
- `operator_approval_action_total`

Labels:

- `action_name`
- `outcome`
- `review_type`

### Queue and audit visibility

Purpose:

- show queue depth;
- show audit report requests;
- show review activity.

Signals:

- `queue_item_count`
- `audit_report_request_total`

Related routes:

```text
GET /workflows/{workflow_run_id}/queue
GET /workflows/{workflow_run_id}/dashboard/queue
GET /workflows/{workflow_run_id}/audit
```

## Required alert candidates

Alert candidates:

- healthcheck failure;
- readiness failure;
- repeated 5xx responses;
- database connection failure;
- migration readiness failure;
- protected route access anomaly;
- queue growth above expected threshold;
- workflow failure spike;
- operator approval failure spike;
- audit report request failure;
- missing observability contract response.

## Alert response guidance

Alert response should:

1. identify affected environment;
2. identify affected route or signal;
3. confirm whether readiness is still true;
4. confirm whether protected routes remain protected;
5. check recent deployment or configuration changes;
6. check rollback runbook when user impact is likely;
7. record outcome and follow-up owner.

References:

```text
docs/operations/p8-step-03.md
docs/operations/p8-step-04.md
```

## Label policy

Only bounded labels from the P7 contract are allowed:

- `route_name`
- `status_family`
- `outcome`
- `action_name`
- `review_type`

Disallowed labels:

- raw workflow id;
- raw operator key;
- request body;
- secret value;
- unbounded free-text error body;
- private runtime value.

## Dashboard boundaries

This step does not choose:

- dashboard vendor;
- metrics collector;
- log aggregation vendor;
- incident management vendor;
- alert routing vendor.

## Guardrails

- No secret values in dashboards.
- No private runtime values in dashboards.
- No raw operator key in telemetry.
- No full request body in telemetry.
- No unbounded label values.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.
- No public production launch.

## Validation

Covered by:

```text
tests/integration/test_p8_step_05.py
```

The validation checks source contract references, dashboard panels, metrics, labels, alert candidates, response guidance, boundaries, and guardrails.
