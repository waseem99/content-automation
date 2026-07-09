# P29 Step 03

Part of #331. Closes #364 after the batch PR merges.

## Goal

Define a publish-readiness manifest that combines package completeness, packaging quality, monetization risk, platform export status, and human approval state.

## Required manifest fields

- `content_package_path`
- `risk_report_path`
- `export_paths`
- `editorial_status`
- `approval_owner`
- `approval_timestamp`
- `blockers`
- `next_actions`

## Readiness states

The manifest can state:

- `not_publish_ready`
- `review_required`
- `publish_export_ready`

## Alignment

The manifest aligns with:

- P24 content package output;
- P25 packaging and retention quality;
- P26 monetization and publish-block risk rules;
- P27 platform export packs;
- P29 human editorial approval.

Platform export is not the same as actual upload. A platform export pack may be ready while the system still has no permission to publish externally.

## Example

```text
docs/operations/p29-publish-readiness-manifest-example.json
```

## Validation

```text
src/p29_governance.py
tests/integration/test_p29_batch_02_06.py
```

## Stop conditions

Stop if a future change attempts to:

- implement real user authentication in this step;
- upload to platforms;
- treat P27 exports as direct publishing;
- set `publish_allowed` to `true`;
- bypass P26 risk clearance;
- bypass P29 human approval.
