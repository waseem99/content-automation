# P32 Step 04

Part of #427. Closes #431 after the batch PR merges.

## Goal

Define failure, warning, and exit-code semantics for local operator dry-run commands.

## Exit codes

| Case | Code |
| --- | --- |
| `success` | 0 |
| `validation_failure` | 1 |
| `governance_block` | 2 |
| `missing_artifact` | 3 |
| `unsafe_mode_request` | 4 |
| `internal_error` | 5 |

## Warning categories

- `missing_optional_artifact`
- `stale_input`
- `review_required`
- `risk_warning`
- `export_warning`

## Blocking categories

- `publish_block`
- `rights_block`
- `unsafe_mode_block`
- `credential_request_block`

## Safety boundary

Unsafe requests fail closed. This step does not implement shell execution or a runtime exception framework.

## Example

```text
docs/operations/p32-local-operator-cli-example.json
```
