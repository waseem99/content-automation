# P35 Step 02

Part of #451. Closes #453 after the batch PR merges.

## Goal

Implement local artifact inventory metadata for materialized review artifacts.

## Inventory entry fields

- `artifact_name`
- `relative_path`
- `checksum`
- `byte_count`
- `content_type`
- `source_command`
- `local_only`
- `review_required`

## Inventory document fields

- `schema_version`
- `inventory_id`
- `generated_at`
- `entries`
- `warnings`
- `guardrails`

## Safety boundary

The inventory is a local metadata document only. It does not write to external registries, sync cloud storage, or use a persistent database.
