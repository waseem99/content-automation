# P34 Step 05

Part of #443. Closes #448 after the batch PR merges.

## Goal

Implement blocked path and overwrite-safety handling for local artifact materialization.

## Rules

- Unsafe artifact names return structured blocked metadata.
- Out-of-root paths fail closed.
- Existing files are not overwritten by default.
- Same-path replacement requires `allow_overwrite=True`.
- Unsafe writes should not create partial files.

## Safety boundary

P34 does not introduce recursive deletion, cleanup jobs, destructive overwrite flows, cloud sync, upload, or publishing behavior.
