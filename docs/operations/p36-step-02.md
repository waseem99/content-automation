# P36 Step 02

Part of #459. Closes #461 after the batch PR merges.

## Goal

Define packet index and section summary metadata for local human review packets.

## Packet fields

- `schema_version`
- `packet_id`
- `generated_at`
- `packet_title`
- `items`
- `sections`
- `counts`
- `warnings`
- `guardrails`

## Sections

- `executive_summary`
- `review_required`
- `ready_for_approval`
- `blocked`
- `reference_artifacts`

## Safety boundary

The packet index is metadata only. It does not render HTML/PDF, generate ZIP archives, upload externally, or publish.
