# P9 Step 04

This step documents dashboard review and alert routing rehearsal expectations before production rollout.

Part of #131. Closes #135 after the PR merges.

## Goal

Rehearse operational visibility and alert routing expectations before any controlled production rollout decision.

## Source references

This review builds on:

```text
docs/operations/p8-step-05.md
docs/operations/p9-step-01.md
docs/operations/p9-step-03.md
```

## Review scope

The review covers:

- dashboard panel availability;
- metric and label review;
- health and readiness signal review;
- workflow and operator action signal review;
- queue and audit visibility review;
- alert candidate review;
- alert routing rehearsal;
- evidence capture;
- guardrail review.

This review does not select a dashboard vendor, metrics collector, log aggregation vendor, incident management vendor, or alert routing vendor.

## Participants

Recommended participants:

- dashboard reviewer;
- alert routing reviewer;
- deployment operator;
- decision owner;
- evidence reviewer.

## Dashboard panel checks

Required panels:

- service health;
- readiness and migration state;
- API request volume and latency;
- workflow and operator actions;
- queue and audit visibility.

Required signals:

- `runtime_startup_total`
- `runtime_healthcheck_total`
- `runtime_readiness_total`
- `api_request_total`
- `api_request_duration_ms`
- `workflow_action_total`
- `operator_approval_action_total`
- `queue_item_count`
- `audit_report_request_total`

## Label checks

Allowed bounded labels:

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
- private runtime value;
- unbounded free-text error body.

## Alert candidate checks

Required alert candidates:

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

## Alert routing rehearsal

Alert routing rehearsal should confirm:

1. alert owner or group is identified;
2. route for healthcheck failure is known;
3. route for readiness failure is known;
4. route for database or migration failure is known;
5. route for protected route access anomaly is known;
6. route for workflow failure spike is known;
7. route for rollback decision owner is known;
8. escalation path is recorded;
9. acknowledgement expectation is recorded;
10. no secret values are included in alert payloads.

## Runtime route review

Review these runtime routes:

```text
GET /health
GET /runtime/ready
GET /runtime/config
GET /runtime/observability
```

Review these operator visibility routes:

```text
GET /workflows/{workflow_run_id}/queue
GET /workflows/{workflow_run_id}/dashboard/queue
GET /workflows/{workflow_run_id}/audit
```

## Evidence capture

Record:

- dashboard review date;
- reviewed panels;
- reviewed signal list;
- label policy result;
- alert candidate list;
- routing owner or group for each alert family;
- escalation path;
- runtime route review result;
- operator route review result;
- unresolved gaps and owner.

Do not record alert payload secrets, private runtime values, raw operator keys, or full request bodies.

## Stop conditions

Stop the rollout decision if:

- readiness signal is unavailable;
- healthcheck signal is unavailable;
- alert owner is unknown;
- rollback owner is unknown;
- protected route alert path is unknown;
- dashboards expose secret values;
- dashboards use unbounded labels;
- alert payload includes private runtime values.

## Guardrails

- No secret values in dashboards.
- No private runtime values in dashboards.
- No raw operator key in telemetry.
- No full request body in telemetry.
- No unbounded label values.
- No public production launch.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.

## Validation

Covered by:

```text
tests/integration/test_p9_step_04.py
```

The validation checks source references, panel checks, labels, alert candidates, routing rehearsal, route review, evidence capture, stop conditions, and guardrails.
