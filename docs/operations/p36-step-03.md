# P36 Step 03

Part of #459. Closes #462 after the batch PR merges.

## Goal

Define reviewer checklist and decision gate metadata for local review packets.

## Gates

- `completeness`
- `governance`
- `integrity`
- `retention`
- `blocker_review`
- `final_operator_decision`

## Decision options

- `approve_local_packet`
- `request_changes`
- `hold_blocked`
- `archive_candidate_review`

## Safety boundary

Approval remains human-only and local-only. P36 does not implement approval automation, digital signatures, external review tools, upload, sync, or publishing.
