# Stage Product Worker

P2-04 adds the first structured output worker after packet approval.

## Flow

1. Packet is created from intake.
2. Packet approval is recorded through the P2-03 prerequisite layer.
3. `StageProductService.create_for_packet` calls `require_packet_approved`.
4. Missing, pending, change-requested, or rejected status blocks execution.
5. Approved packets produce a structured output row.
6. The row is stored with workflow, intake, packet, worker stage, output hash, citations, outline, narration, and `review_required` status.

## Stored output

- title
- hook
- outline
- narration
- citation map
- metadata

## Guardrails

- Duplicate worker input reuses the existing stage output.
- The stored row remains in `review_required` status before any later step consumes it.
- This PR does not add storyboard, publishing, or final approval logic.
