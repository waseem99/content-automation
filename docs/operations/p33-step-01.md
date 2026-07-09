# P33 Step 01

Part of #435. Closes #436 after the batch PR merges.

## Goal

Implement a safe local CLI argument parser and command dispatcher for the supported P32 commands.

## Supported commands

- `validate-package`
- `review-readiness`
- `build-report`
- `export-handoff`
- `dry-run-publish-check`
- `closeout-check`

## Runtime helper

```text
src/p33_cli_runtime.py
```

## Parser fields

- `command`
- `--input`
- `--output-dir`
- `--mode`
- `--require-inputs`

## Safety boundary

The dispatcher only builds local dry-run result payloads. It does not install console scripts, call external services, upload files, or publish content.
