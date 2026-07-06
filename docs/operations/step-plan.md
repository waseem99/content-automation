# Step Plan Worker

P2-05 adds the planning worker after reviewed structured output.

## Flow

1. A structured output is created from an approved packet.
2. A source-output review marker is requested.
3. Planning is blocked until that marker is approved.
4. Approved source output creates a plan row.
5. The plan stores scenes, requirements, notes, metadata, workflow context, source output, packet, intake, worker stage, and output hash.

## Guardrails

- Missing or pending review blocks planning.
- The worker only creates a plan; it does not attach or approve media.
- Every requirement is marked for rights review.
- Duplicate worker input reuses the existing plan row.

## Non-goals

- Rendering.
- Publishing.
- Final media approval.
