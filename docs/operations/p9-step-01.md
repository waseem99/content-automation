# P9 Step 01

This step documents a controlled deployment dry-run rehearsal for the operator runtime.

Part of #131. Closes #132 after the PR merges.

## Goal

Rehearse production rollout mechanics without opening public production access or bypassing workflow gates.

## Source references

This runbook builds on:

```text
docs/operations/p8-step-01.md
docs/operations/p8-step-02.md
.env.production.example
```

## Dry-run scope

The dry-run covers:

- service image build expectations;
- runtime command verification;
- environment variable review;
- health check verification;
- readiness verification;
- safe configuration snapshot review;
- observability contract verification;
- protected route access check;
- stop conditions;
- evidence capture.

The dry-run does not launch public production traffic.

## Participants

Recommended participants:

- deployment operator;
- database operator;
- reviewer for configuration and evidence;
- decision owner for go/no-go status.

## Preparation checklist

Before the dry-run:

1. Confirm target environment name.
2. Confirm deployment image tag or digest.
3. Confirm runtime command is `uvicorn src.operator_api.entrypoint:app --host 0.0.0.0 --port 8000`.
4. Confirm `DATABASE_REQUIRE_SCHEMA=true` for production-like rehearsal.
5. Confirm `OPERATOR_RUNTIME_DATABASE_REQUIRE_SCHEMA=true`.
6. Confirm `.env.production.example` has no real secrets.
7. Confirm secrets are injected outside git.
8. Confirm migrations have been reviewed.
9. Confirm backup and restore runbook is available.
10. Confirm rollback runbook is available.

## Execution steps

Deployment dry-run steps:

1. Build or select the candidate runtime image.
2. Start the runtime with production-like non-public configuration.
3. Keep external exposure private or internal.
4. Confirm the process listens on port `8000`.
5. Confirm `GET /health` succeeds.
6. Confirm `GET /runtime/config` returns safe configuration only.
7. Confirm `GET /runtime/ready` returns `ok: true`.
8. Confirm `GET /runtime/observability` returns the telemetry contract.
9. Confirm protected routes require operator access.
10. Record image tag or digest, environment name, operator, reviewer, and result.

## Verification checks

Required verification:

- liveness route responds;
- readiness route reports healthy database and migration state;
- safe configuration route does not expose secrets;
- observability route returns metric and event contract;
- protected routes reject unauthenticated access;
- logs do not include secret values;
- workflow gates remain enforced.

## Stop conditions

Stop the dry-run if any of these occur:

- `GET /health` fails;
- `GET /runtime/ready` does not return `ok: true`;
- migration readiness fails;
- runtime config exposes a secret value;
- protected route access is not enforced;
- observability contract is missing;
- deployment requires workflow gate bypass;
- rollback owner is unavailable.

## Evidence capture

Record:

- environment name;
- image tag or digest;
- commit SHA;
- runtime command;
- health result;
- readiness result;
- config snapshot review result;
- observability contract review result;
- protected route access result;
- stop condition result;
- reviewer name or role.

Do not record secret values.

## Guardrails

- No public production launch.
- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.
- No secret values in logs.
- No private runtime values in evidence.

## Validation

Covered by:

```text
tests/integration/test_p9_step_01.py
```

The validation checks source references, preparation, execution, health and readiness checks, stop conditions, evidence capture, guardrails, and P9 CI wildcard coverage.
