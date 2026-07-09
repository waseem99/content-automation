# P36 Step 01

Part of #459. Closes #460 after the batch PR merges.

## Goal

Define local review packet item metadata for artifacts, reports, inventories, summaries, and blocker appendices.

## Item fields

- `item_id`
- `title`
- `relative_path`
- `item_type`
- `source_system`
- `source_issue`
- `review_status`
- `reviewer_role`
- `required`
- `checksum_digest`

## Supported item types

- `report`
- `cli_result`
- `artifact`
- `inventory`
- `summary`
- `blocker_appendix`
- `checklist`

## Safety boundary

Packet item metadata is local-only and review-required. It does not read files, generate ZIP archives, upload, sync, deliver, delete, move, or publish.
