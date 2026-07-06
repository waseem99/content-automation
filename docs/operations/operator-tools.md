# Operator Review Tools

P2-06 adds operator-facing tools for the P2 review chain.

## Queue

`python -m src.infrastructure.database.cli operator queue --workflow-run-id <id> --json`

The queue surfaces:

- packet reviews that are not approved,
- structured outputs that need output review,
- created step plans that still need human attention.

## Packet approval

`python -m src.infrastructure.database.cli operator approve-packet --workflow-run-id <id> --packet-id <id> --reviewed-by <name>`

This records the packet as approved through the existing prerequisite service.

## Output review

`python -m src.infrastructure.database.cli operator request-output --workflow-run-id <id> --source-output-id <id>`

`python -m src.infrastructure.database.cli operator approve-output --workflow-run-id <id> --source-output-id <id> --reviewed-by <name>`

Approved outputs can be consumed by the step-plan worker.

## Guardrails

- The tools only change review status.
- They do not generate new content, attach media, render, or publish.
- Plan rows remain review-required after creation.
