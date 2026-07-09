# P31 Step 05

Part of #419. Closes #424 after the batch PR merges.

## Goal

Define the operator handoff/export report package so weekly briefs, action queues, and exception reports can be shared as reviewable artifacts.

## Required fields

- `package_id`
- `reporting_period`
- `generated_at`
- `files`
- `audience`
- `review_required`
- `distribution_note`
- `next_operator_steps`

## Required files

- `weekly_brief.json`
- `decision_queue.json`
- `governance_exceptions.json`
- `operator_summary.md`

## Safety boundary

The package is local/review-only. It does not email, post to Slack, publish a dashboard, or upload files externally.

## Example

```text
docs/operations/p31-operator-reporting-example.json
```
