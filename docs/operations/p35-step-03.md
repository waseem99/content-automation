# P35 Step 03

Part of #451. Closes #454 after the batch PR merges.

## Goal

Implement retention policy metadata that documents retention intent without deleting, moving, archiving, or syncing files.

## Retention fields

- `policy_id`
- `retention_class`
- `review_after_days`
- `owner_role`
- `reason`
- `deletion_allowed`
- `manual_review_required`

## Supported retention classes

- `keep`
- `review_later`
- `archive_candidate`
- `legal_hold`

## Safety boundary

P35 keeps `deletion_allowed` false. It does not delete files, move files, archive files, or run a retention scheduler.
