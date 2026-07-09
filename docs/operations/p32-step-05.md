# P32 Step 05

Part of #427. Closes #432 after the batch PR merges.

## Goal

Define the local operator runbook and handoff checklist for running dry-run validations and preparing reviewable artifacts.

## Runbook steps

1. `collect_inputs`
2. `run_validation`
3. `review_warnings`
4. `resolve_blockers`
5. `build_report`
6. `prepare_handoff`
7. `record_decision`

## Handoff checklist

- `artifacts_included`
- `warnings_reviewed`
- `blockers_resolved_or_documented`
- `review_owner_assigned`
- `no_external_action_performed`

## Safety boundary

Operators must not publish, upload, schedule, notify, sync accounts, store credentials, or delete assets from this runbook.

## Example

```text
docs/operations/p32-local-operator-cli-example.json
```
