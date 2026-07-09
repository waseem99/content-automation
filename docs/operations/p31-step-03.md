# P31 Step 03

Part of #419. Closes #422 after the batch PR merges.

## Goal

Define a content decision queue that turns analytics feedback and governance states into clear next actions for operators.

## Required fields

- `item_id`
- `content_id`
- `decision_type`
- `priority`
- `reason`
- `source_signal`
- `recommended_action`
- `owner_role`
- `due_window`
- `review_status`

## Decision types

- `repeat`
- `revise`
- `expand`
- `hold`
- `archive`
- `escalate_rights`
- `escalate_risk`
- `prepare_export`

## Safety boundary

The decision queue is advisory. No action is automatically executed, scheduled, published, archived, or escalated outside the report.

## Example

```text
docs/operations/p31-operator-reporting-example.json
```
