# P32 Step 02

Part of #427. Closes #429 after the batch PR merges.

## Goal

Define dry-run execution behavior and safety flags so local operator commands cannot be mistaken for live publishing or external integrations.

## Required flags

- `dry_run`
- `no_network`
- `no_upload`
- `no_scheduler`
- `no_credentials`
- `no_external_notifications`
- `read_only_inputs`

## Allowed modes

- `inspect`
- `validate`
- `build-local-artifact`
- `package-local-handoff`

## Blocked modes

- `upload`
- `publish`
- `schedule`
- `notify`
- `delete`
- `sync-account`

## Safety boundary

Dry-run commands do not perform external actions. Unsafe modes must fail closed.

## Example

```text
docs/operations/p32-local-operator-cli-example.json
```
