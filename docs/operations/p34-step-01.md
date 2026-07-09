# P34 Step 01

Part of #443. Closes #444 after the batch PR merges.

## Goal

Implement safe output-root and path validation for local artifact materialization.

## Rules

- Accept an explicit allowed output root.
- Reject absolute paths.
- Reject parent traversal.
- Reject home expansion.
- Reject URL-like paths.
- Reject backslash separators.
- Resolve candidate paths under the allowed output root only.

## Runtime helper

```text
src/p34_artifacts.py
```

## Safety boundary

Path validation fails closed and does not upload, sync, delete, publish, or call external services.
