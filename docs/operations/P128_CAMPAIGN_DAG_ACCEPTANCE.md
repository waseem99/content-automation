# P128 Campaign DAG Acceptance

P128 keeps PostgreSQL as the only queue and state database. It adds campaign-level DAGs above the existing immutable job-attempt principles without introducing Redis, NATS, spreadsheets or a second operational store.

## Measured gate

The full workflow creates:

- 10 isolated active campaign graphs;
- 1,000,000 retained two-stage tasks;
- 500,000 one-to-one dependency edges;
- 100 registered capability-aware workers;
- a fair 1,000-task `SKIP LOCKED` claim sample;
- a paused-graph isolation check;
- 100 deliberately expired leases followed by recovery and exact restart reclaim;
- one successful retained attempt for every task, with zero duplicate successful attempts.

## Safety boundaries

The benchmark uses synthetic control-plane payloads. It does not render media, contact providers, reserve paid spend or publish content. The result proves database orchestration behavior only; renderer throughput remains separately measured.

## Runtime behavior

Workers declare normalized capabilities and concurrency. Claims are bounded by worker capacity, require all task capabilities, ignore paused/cancelled graphs, and skip tasks whose dependencies have not succeeded. Completion is lease-bound and idempotent. Stale attempts become timed out and are either requeued or dead-lettered after the configured attempt ceiling.
