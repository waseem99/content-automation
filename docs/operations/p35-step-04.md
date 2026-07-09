# P35 Step 04

Part of #451. Closes #455 after the batch PR merges.

## Goal

Implement integrity verification that compares current local artifact metadata against inventory entries without modifying files.

## Statuses

- `match`
- `missing`
- `changed`
- `unexpected`

## Verification output

- inventory id;
- generated time;
- per-artifact results;
- status counts;
- warnings;
- guardrails.

## Safety boundary

Verification is read-only and metadata-only. It does not repair, delete, move, sync, upload, or monitor files in the background.
