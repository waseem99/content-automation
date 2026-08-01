# P129 Storage Scale and Recovery

PostgreSQL remains the canonical asset, checksum, lineage and location store. Physical providers remain restricted to local storage and optional Google Drive copies.

## Full acceptance gate

The workflow retains and verifies:

- 50,000 canonical assets;
- exactly 100,000 location records: one local and one Google Drive record per asset;
- canonical SHA-256 and size equality across every retained location;
- zero unsupported storage providers;
- zero duplicate location rows after an idempotent duplicate probe;
- a real available local file;
- a real checksum-mismatched local file;
- a real missing local file;
- three verified Drive metadata/download samples through a deterministic adapter;
- full missing-local recovery from Drive with SHA-256, size and atomic replacement;
- unchanged asset IDs and canonical hashes;
- local reconciliation continuing without calling Drive during a simulated Drive outage.

The 100,000-record portion is a database control-plane benchmark. Real filesystem and Drive semantics are tested on canonical sample assets so the workflow does not pretend to transfer 100,000 remote objects in CI.

## Recovery behavior

Recovery is permitted only when a local location is missing or mismatched and an available Drive location exists for the same canonical asset. The Drive metadata, downloaded bytes, SHA-256 and size must all match the asset registry before the local location becomes available. Every success or failure is recorded as immutable recovery evidence.
