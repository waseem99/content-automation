# P7 Step 03

This step adds a lightweight observability instrumentation surface for the operator runtime.

Part of #105. Closes #108 after the PR merges.

## Goal

Provide stable internal event and metric shapes that can be used by future logging, metrics, and alerting work without selecting an external collector.

## Runtime contract route

Use:

```text
GET /runtime/observability
```

Expected response fields:

- `ok`
- `kind`
- `service`
- `event_fields`
- `metric_names`
- `label_fields`
- `guardrails`

Expected `kind` value:

```text
runtime_observability_contract
```

## Event shape

Runtime events use safe fields only:

- `level`
- `event_name`
- `service`
- `request_id`
- `workflow_id`
- `operator_id`
- `route_name`
- `status_code`
- `outcome`
- `duration_ms`
- `error_type`
- `error_summary`

Future log emitters may add a timestamp and runtime environment at emission time.

## Metric shape

Runtime metrics use:

- `name`
- `value`
- `labels`

Supported metric names:

- `runtime_startup_total`
- `runtime_healthcheck_total`
- `runtime_readiness_total`
- `api_request_total`
- `api_request_duration_ms`
- `workflow_action_total`
- `operator_approval_action_total`
- `audit_report_request_total`
- `queue_item_count`

## Label policy

Supported labels are intentionally bounded:

- `route_name`
- `status_family`
- `outcome`
- `action_name`
- `review_type`

Unsupported labels fail closed in the helper surface.

## Operator usage

Operators can use the contract route to confirm which fields and metrics are safe to instrument before wiring any future collector or dashboard.

## Out of scope

- No external collector is added.
- No metrics service is added.
- No vendor choice is made.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.

## Guardrails

- No full request body.
- No private runtime values.
- No raw operator key.
- No unbounded label values.
- No external collector required.

## Validation

Covered by:

```text
tests/integration/test_p7_step_03.py
```

The validation checks the observability contract route, event helper, metric helper, bounded labels, documentation, and guardrails.
