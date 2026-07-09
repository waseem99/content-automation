# P32 Step 03

Part of #427. Closes #430 after the batch PR merges.

## Goal

Define the input and output artifact contract for each local operator command.

## Required artifact fields

- `command_name`
- `input_artifacts`
- `output_artifacts`
- `required_paths`
- `optional_paths`
- `generated_manifest`
- `operator_summary`
- `validation_report`

## Covered artifacts

- content packages;
- export packs;
- publish-readiness manifests;
- analytics feedback;
- operator reports;
- handoff packages.

## Safety boundary

Outputs are local/review-only artifacts. No external upload, cloud sync, or permanent artifact database is introduced.

## Example

```text
docs/operations/p32-local-operator-cli-example.json
```
