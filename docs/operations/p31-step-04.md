# P31 Step 04

Part of #419. Closes #423 after the batch PR merges.

## Goal

Define a risk and governance exception report that highlights blocked, review-required, rights-risk, source-risk, or publish-governance issues for operators.

## Required fields

- `exception_id`
- `content_id`
- `severity`
- `blocker_type`
- `governance_source`
- `current_status`
- `required_resolution`
- `owner_role`
- `review_notes`

## Severity levels

- `low`
- `medium`
- `high`
- `critical`

## Governance sources

The report can surface issues from P26 risk checks, P27 export warnings, P29 editorial status, and P30 blocked-from-learning outcomes.

## Safety boundary

Exceptions do not trigger automatic publishing, deletion, takedowns, or platform changes.

## Example

```text
docs/operations/p31-operator-reporting-example.json
```
