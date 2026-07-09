# P30 Step 03

Part of #411. Closes #414 after the batch PR merges.

## Goal

Define rules that translate performance learning snapshots into advisory topic-score feedback and future recommendation adjustments.

## P28 scoring links

Feedback can adjust or inform these P28 scoring dimensions:

- `timeliness`
- `emotional_intensity`
- `comment_potential`
- `series_fit`
- `monetization_fit`
- `production_effort`

## Recommendation outputs

- `repeat_format`
- `refine_angle`
- `expand_to_long_form`
- `create_follow_up_short`
- `hold`
- `reject_or_archive`

## Safety boundary

Recommendations are advisory and human-reviewed. They do not automatically create topics, schedule content, publish content, or scrape live trends.

## Example

```text
docs/operations/p30-analytics-feedback-example.json
```
