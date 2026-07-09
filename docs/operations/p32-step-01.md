# P32 Step 01

Part of #427. Closes #428 after the batch PR merges.

## Goal

Define the local operator command registry for package validation, governance checks, report building, handoff export, and dry-run publish checks.

## Required commands

- `validate-package`
- `review-readiness`
- `build-report`
- `export-handoff`
- `dry-run-publish-check`
- `closeout-check`

## Required command fields

- `command_name`
- `purpose`
- `required_inputs`
- `outputs`
- `allowed_modes`
- `safety_flags`

## Safety boundary

No command uploads, publishes, schedules, notifies, syncs accounts, or calls external services.

## Example

```text
docs/operations/p32-local-operator-cli-example.json
```
