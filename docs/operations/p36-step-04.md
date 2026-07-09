# P36 Step 04

Part of #459. Closes #463 after the batch PR merges.

## Goal

Define risk and blocker appendix semantics for local review packets.

## Blocker fields

- `appendix_id`
- `blocker_type`
- `severity`
- `source_item_id`
- `source_issue`
- `current_status`
- `required_resolution`
- `owner_role`
- `reviewer_notes`

## Blocker types

- `governance_block`
- `integrity_drift`
- `retention_review`
- `missing_artifact`
- `rights_review`
- `unsafe_publish_state`

## Safety boundary

Blockers are advisory and review-only. No automated remediation, deletion, upload, sync, platform change, or publishing action is performed.
