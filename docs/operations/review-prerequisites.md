# Review Prerequisites

P2-03 adds a stored prerequisite layer between packet creation and draft work.

## Flow

1. A packet is created from an intake.
2. The packet is submitted for review.
3. Draft work calls `require_packet_approved` before using the packet.
4. Pending, change-requested, rejected, or missing review status blocks draft work.
5. Approved status allows the packet to be consumed by later draft workers.

## Stored status values

- `pending`
- `approved`
- `changes_requested`
- `rejected`

## Events

- `review_prerequisite_requested`
- `review_prerequisite_decided`

## Non-goals

- Draft generation.
- Script approval workflow.
- Publishing.
