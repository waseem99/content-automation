# Worker Contracts

Issue #9 adds a synchronous worker execution layer on top of the existing PostgreSQL workflow foundation.

## Guarantees

- Worker definitions include name, version, schema names/versions, timeout, cost estimate, retry policy and idempotency fields.
- Canonical worker input hashing includes worker name/version and schema versions.
- Idempotency fields let workers exclude irrelevant runtime values from the execution key.
- `stage_executions.idempotency_key` is the duplicate-execution guard.
- Completed stages with the same worker key are reused without invoking the handler again.
- Running duplicate submissions return an `already_running` result.
- Worker success transitions the stage through the workflow state machine and stores output hash/output payload.
- Provider-backed workers can write a provider-call ledger row keyed by provider and worker idempotency key.
- Retry policy helpers classify retryable and non-retryable failures; retry attempts remain separate stage executions through the state machine foundation.

## Current reference workers

- `transcription_stub`
- `voice_stub`

These are deterministic local workers for CI and integration wiring. Production provider wrappers should implement the same `WorkerHandlerResult` contract and must not put secrets into input or output payloads.

## Follow-on integration

Future workers for real transcription, image generation, voice generation and rendering should register definitions in the worker registry, then run through `WorkerDispatcher.execute` rather than calling providers directly.
