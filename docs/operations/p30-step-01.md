# P30 Step 01

Part of #411. Closes #412 after the batch PR merges.

## Goal

Define a platform-agnostic performance metrics input contract that can be filled manually or imported later without connecting live platform APIs.

## Required metrics fields

- `platform`
- `content_id`
- `published_external_url`
- `publish_date`
- `views`
- `watch_time_seconds`
- `average_view_duration_seconds`
- `retention_rate`
- `likes`
- `comments`
- `shares`
- `saves`
- `click_through_rate`
- `subscribers_gained`
- `revenue_estimate`
- `manual_notes`
- `review_state`
- `data_quality`

## Supported content formats

- `shorts`
- `explainer`
- `long_form`

## Safety boundary

This step supports manual or fixture-based metrics only.

It does not:

- ingest live analytics APIs;
- implement OAuth;
- store platform credentials;
- ingest real account data automatically;
- make publishing decisions.

## Example

```text
docs/operations/p30-analytics-feedback-example.json
```

## Validation

```text
src/p30_analytics.py
tests/integration/test_p30_batch_01_06.py
```
