# P7 Step 05

This step updates operator runbook notes for the P7 runtime path.

Part of #105. Closes #110 after the PR merges.

## Goal

Give operators a single P7 checklist that uses the container package, health and readiness checks, observability contract, static UI route map, and existing pilot flow.

## Prerequisites

Before running the P7 operator path:

- dependencies are available;
- `.env` is prepared from `.env.example`;
- database settings are configured;
- migrations are applied;
- operator access is configured for protected routes;
- P1 Acceptance Harness is green on the latest merged head.

## Step 1: Build runtime package

```bash
docker build -t content-automation-operator:local .
```

Expected result:

- image builds from `Dockerfile`;
- dependencies install from `requirements.txt`;
- runtime entrypoint remains `src.operator_api.entrypoint:app`.

## Step 2: Start runtime package

```bash
docker run --rm -p 8000:8000 --env-file .env content-automation-operator:local
```

Expected result:

- runtime starts on port `8000`;
- no private runtime values are printed;
- no publishing, scheduling, rendering, or external export starts.

## Step 3: Check liveness

```text
GET /health
```

Expected result:

- `ok` is true;
- service name is present;
- version is present;
- database configured flag is present;
- access required flag is present.

## Step 4: Check runtime config

```text
GET /runtime/config
```

Expected result:

- runtime snapshot is returned;
- no private runtime values are returned.

## Step 5: Check readiness

```text
GET /runtime/ready
```

Expected result:

- readiness returns `ok: true` before operator workflow actions begin;
- checks include database configured, database reachable, schema required, schema ready, and migrations ready.

## Step 6: Check observability contract

```text
GET /runtime/observability
```

Expected result:

- event fields are present;
- metric names are present;
- label fields are bounded;
- guardrails are present.

## Step 7: Use static UI route map

Reference:

```text
docs/operations/p7-step-04.md
```

Operator screens:

- runtime status;
- queue;
- demo run;
- audit report;
- guardrails.

## Step 8: Run the existing pilot flow

Reference:

```text
docs/operations/p6-step-05.md
```

Pilot sequence:

1. prepare workflow id;
2. load demo scenario;
3. start demo run;
4. approve packet gate explicitly;
5. approve output gate explicitly;
6. confirm final stop point at `continue_p3_delivery`;
7. inspect audit report;
8. record result.

## Pass criteria

The P7 operator path passes when:

- package builds;
- runtime starts;
- liveness succeeds;
- runtime config is available;
- readiness succeeds;
- observability contract is available;
- static UI route map is followed;
- pilot flow reaches the expected stop point;
- audit report includes expected review and timeline data.

## Fail criteria

The P7 operator path fails when:

- package build fails;
- runtime cannot start;
- liveness fails;
- readiness returns HTTP 503;
- observability contract is missing;
- protected routes work without operator access;
- pilot flow skips a review gate;
- any non-goal action is triggered.

## Guardrails

- No publishing.
- No scheduling.
- No rendering.
- No external export.
- No workflow gate bypass.
- No automatic approval.
- No public production launch.
- No private runtime values.

## Validation

Covered by:

```text
tests/integration/test_p7_step_05.py
```

The validation checks package steps, liveness, readiness, observability, static UI route map, pilot flow references, pass/fail criteria, and guardrails.
