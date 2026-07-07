# P6 Step 04

This step adds a minimal static operator UI shell against the P5 UI contract.

No frontend framework, build system, or hidden business logic is added.

## Files

- `src/operator_ui/static/index.html`
- `src/operator_ui/static/styles.css`
- `tests/integration/test_p6_step_04.py`

## Screens included

- Runtime status
- Queue
- Demo run
- Audit report
- Guardrails

## API route mapping

The static shell maps these existing P5 routes:

- `GET /health`
- `GET /runtime/config`
- `GET /workflows/{workflow_run_id}/queue`
- `GET /workflows/{workflow_run_id}/dashboard/queue`
- `GET /demo/scenario`
- `POST /demo/{workflow_run_id}/start`
- `POST /demo/{workflow_run_id}/approve-current`
- `GET /demo/{workflow_run_id}/status`
- `GET /workflows/{workflow_run_id}/audit`

## Design intent

The shell provides screen structure, field placeholders, route references, and user-visible action labels. It does not implement API calls yet.

## Guardrails

- No frontend framework is added.
- No build step is added.
- No API route is added.
- No publishing action is present.
- No scheduling action is present.
- No rendering action is present.
- No external export action is present.
- No workflow gate is bypassed.

## Validation

Covered by:

```text
tests/integration/test_p6_step_04.py
```

The validation checks that the static shell includes the required screens, route references, fields, action labels, stylesheet link, and guardrails.
