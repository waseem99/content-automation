# P33 Step 02

Part of #435. Closes #437 after the batch PR merges.

## Goal

Enforce dry-run-only safety behavior and fail closed when an operator requests blocked modes or unsafe flags.

## Blocked modes

- `upload`
- `publish`
- `schedule`
- `notify`
- `delete`
- `sync-account`

## Unsafe flags

- `--allow-network`
- `--allow-upload`
- `--allow-scheduler`
- `--allow-credentials`
- `--allow-notifications`
- `--allow-delete`

## Exit code

Blocked unsafe requests return the P32 `unsafe_mode_request` code:

```text
4
```

## Safety boundary

No external action is performed. Unsafe requests fail closed before command dispatch.
