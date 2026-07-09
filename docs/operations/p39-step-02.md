# P39 Step 02

Part of #483. Closes #485 after merge.

## Goal
Validate supported local decision states.

## States
- `approved_local`
- `request_changes`
- `hold_blocked`
- `archive_candidate_review`

## Safety
Unsupported states fail closed. No automated approval or publishing.
