# P31 Step 01

Part of #419. Closes #420 after the batch PR merges.

## Goal

Define the reporting input bundle that gathers package, export, governance, analytics, and decision context into one operator-readable reporting source.

## Required fields

- `reporting_period`
- `generated_at`
- `content_packages`
- `export_manifests`
- `publish_readiness_manifests`
- `analytics_feedback_snapshots`
- `governance_exceptions`
- `recommendations`
- `operator_notes`

## Upstream links

- P27 export packs
- P28 topic planning
- P29 publish governance
- P30 analytics feedback

## Safety boundary

The bundle is manual/fixture based and review-safe. It does not ingest live analytics, send automated notifications, or trigger publishing.

## Example

```text
docs/operations/p31-operator-reporting-example.json
```
