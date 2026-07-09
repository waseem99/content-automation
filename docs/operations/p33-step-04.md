# P33 Step 04

Part of #435. Closes #439 after the batch PR merges.

## Goal

Implement deterministic JSON output and P32-compatible exit-code mapping for the local CLI runtime.

## Exit codes

| Category | Code |
| --- | --- |
| `success` | 0 |
| `validation_failure` | 1 |
| `governance_block` | 2 |
| `missing_artifact` | 3 |
| `unsafe_mode_request` | 4 |
| `internal_error` | 5 |

## Runtime helpers

- `run_cli(argv)`
- `build_command_result(namespace)`
- `render_json(result)`
- `main(argv)`

## Safety boundary

The JSON helper renders local payloads only. It does not write files externally, call shell commands, upload, notify, schedule, or publish.
