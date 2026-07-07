# P4 Step 01

This step adds a controlled workflow runner for the first operator-driven path.

## Flow

`P4ControlService.run_until_waiting` currently advances through:

1. Intake creation or reuse.
2. Research packet creation or reuse.
3. Packet review request.
4. Source output creation after packet approval.
5. Source output review request.
6. Step-plan creation after source output approval.

The service stops whenever a review is required. It does not approve anything automatically.

## Result shape

The result is JSON-friendly through `P4ControlResult.as_dict()`:

- `workflow_run_id`
- `status`
- `next_action`
- `steps[]`
  - `name`
  - `status`
  - `resource_id`
  - `reason`
  - `metadata`

## Stop points

- `approve_packet` when packet review is pending.
- `approve_output` when source output review is pending.
- `continue_p3_delivery` after the step plan is created.

## Guardrails

- The runner never approves reviews automatically.
- Existing packet and source output review gates remain authoritative.
- P3 delivery controls remain separate and are not bypassed.
- No publishing, scheduling, rendering, or external export is performed.

## Validation

Covered by `tests/integration/test_p4_step_01.py` through the P1 Acceptance Harness P4 wildcard entry.
