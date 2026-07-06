# Brief Builder

P2-02 adds a manual builder for football intakes.

## What it does

- Reads an existing intake record.
- Builds a structured brief with references, draft notes, entities, freshness metadata, and citations.
- Runs through the Phase 1 budgeted worker dispatcher.
- Records provider cost through the existing ledger.
- Stores the brief against the workflow, intake, worker stage, and output hash.

## Guardrails

- The intake must belong to the workflow.
- The intake must be accepted.
- Duplicate worker inputs reuse the existing stage output.
- Budget stop prevents persistence.
- External retrieval is not enabled here; P2-02 uses manual intake references only.

## Non-goals

- Script generation.
- Publication.
- Autonomous discovery.
