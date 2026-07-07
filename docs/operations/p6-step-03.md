# P6 Step 03

This step documents the observability and logging contract for the operator runtime.

No logging framework, collector, or metrics service is added in this step. The goal is to define the contract first.

## Purpose

Runtime operators need enough visibility to answer:

- Is the service healthy?
- Which workflow was affected?
- Which operator action was attempted?
- Where did a request fail?
- Is the runtime producing expected operational signals?

## Structured log fields

Runtime logs should use stable field names where possible.

Required fields:

- timestamp
- level
- event name
- service name
- runtime environment
- request id
- workflow id when available
- operator id when available
- route name when available
- status code when available
- outcome
- duration milliseconds when available

Optional fields:

- queue item type
- review type
- resource id
- next action
- failure reason
- package id
- manifest id

## Request and workflow identifiers

Every inbound API request should carry or receive a request id.

When a workflow id is present in the route or payload, logs should include it.

When a workflow id is not available, logs should still include request id and route name.

## Operator action logging

Operator action logs should include:

- operator id
- action name
- workflow id
- resource id when available
- outcome
- failure reason when the action fails

Operator action logs must not imply automatic approval. They should describe the explicit action that was requested and the result returned by the API contract.

## Error logging expectations

Error logs should include:

- request id
- route name
- workflow id when available
- error type
- safe error summary
- outcome

Error logs should avoid detailed runtime configuration values and full request bodies.

## Safe operational metrics

Future metrics can include:

- request count by route
- response count by status code family
- request duration by route
- queue item count
- workflow run count by status
- approval action count by action and outcome
- audit report request count
- demo run count
- healthcheck success count
- runtime startup count

Metrics should use labels with bounded cardinality.

## Alert candidates

Future alerts can watch for:

- healthcheck failure
- repeated 5xx responses
- repeated access failures
- database connection failures
- migration readiness failures
- queue growth above expected threshold
- workflow failures above expected threshold

## Log levels

Suggested level use:

- DEBUG: local troubleshooting details
- INFO: successful startup, health, normal operator actions
- WARNING: recoverable operational issue
- ERROR: failed request, failed workflow action, database failure
- CRITICAL: runtime cannot serve traffic

## Guardrails

- Do not log detailed runtime values.
- Do not log full request bodies by default.
- Do not add a collector in this step.
- Do not add a metrics service in this step.
- Do not add publishing.
- Do not add scheduling.
- Do not add rendering.
- Do not add external export.

## Validation

Covered by:

```text
tests/integration/test_p6_step_03.py
```

The validation checks that required log fields, identifier guidance, error guidance, safe metrics, alert candidates, and guardrails remain documented.
