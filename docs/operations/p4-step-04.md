# P4 Step 04

This step adds deterministic demo data and notes for the P4 flow.

## Scenario

`P4_DEMO_SCENARIO`

- Scenario id: `p4-demo-derby-preview`
- Title: `P4 Demo Derby Preview`
- Topic: `Derby preview: tactical momentum, selection risks, and match narrative`
- Actor: `demo-operator`
- Source URLs:
  - `https://example.com/p4-demo/derby-preview-source-a`
  - `https://example.com/p4-demo/derby-preview-source-b`

The URLs are static example values. The demo does not fetch them and does not require network access.

## Expected stop points

1. `approve_packet`
2. `approve_output`
3. `continue_p3_delivery`

## Service

`P4DemoService` exposes:

- `scenario()` — returns deterministic scenario metadata.
- `start(workflow_run_id)` — runs the scenario until the next P4 stop point.
- `approve_current(workflow_run_id, reviewed_by, rationale)` — explicitly approves the current supported demo gate.
- `status(workflow_run_id)` — returns the scenario, blocked state, and dashboard queue cards.

## Operator notes

Start the demo:

```python
P4DemoService(database).start(workflow_run_id=workflow_id)
```

Approve packet review:

```python
P4DemoService(database).approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
```

Resume and approve source-output review:

```python
P4DemoService(database).approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")
```

After the second approval, the scenario reaches `continue_p3_delivery` and stops before P3 delivery controls.

## Guardrails

- No external network calls.
- No autonomous approval beyond explicit demo gate calls.
- No publishing, scheduling, rendering, or external export.
- The demo stops before P3 delivery controls.
- Existing P4 dashboard and surface contracts remain authoritative.

## Validation

Covered by `tests/integration/test_p4_step_04.py` through the P1 Acceptance Harness P4 wildcard entry.
