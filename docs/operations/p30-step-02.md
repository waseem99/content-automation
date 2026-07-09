# P30 Step 02

Part of #411. Closes #413 after the batch PR merges.

## Goal

Define a content outcome and learning snapshot schema that summarizes what happened after content was externally published or manually reviewed.

## Required outcome fields

- `content_id`
- `format`
- `platform`
- `performance_window`
- `baseline_comparison`
- `outcome_label`
- `winning_elements`
- `weak_elements`
- `audience_signal_summary`
- `reviewer_interpretation`
- `recommended_follow_up`

## Outcome labels

- `outperforming`
- `average`
- `underperforming`
- `inconclusive`
- `blocked_from_learning`

## Connections

Learning snapshots connect to:

- P28 topic calendar;
- P28 Shorts-to-long-form funnel planning;
- P29 publish-readiness manifest;
- P29 human review state.

## Safety boundary

A snapshot is an editorial interpretation, not automated causal proof.

## Example

```text
docs/operations/p30-analytics-feedback-example.json
```
