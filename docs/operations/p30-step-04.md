# P30 Step 04

Part of #411. Closes #415 after the batch PR merges.

## Goal

Define how analytics feedback produces safe, human-reviewable iteration recommendations for hooks, titles, thumbnails, captions, and packaging.

## Required iteration fields

- `content_id`
- `source_metric_signal`
- `element_type`
- `current_version`
- `proposed_change`
- `rationale`
- `risk_note`
- `expected_learning`
- `review_status`

## Element types

- `hook`
- `title`
- `thumbnail_cover`
- `caption`
- `pinned_comment`
- `description`
- `series_positioning`

## Safety boundary

Iteration recommendations are not automatic content changes. They must remain `review_required` until a human approves them through the P29 governance layer.

## Out of scope

- automatic A/B testing;
- automatic thumbnail generation;
- direct platform edits;
- automatic platform publishing.

## Example

```text
docs/operations/p30-analytics-feedback-example.json
```
