# Budget Controls

Issue #11 adds provider-cost governance before more production infrastructure is added.

## Flow

1. A provider-backed worker request enters the budget-aware dispatcher.
2. The budget service estimates cost using provider, operation, model and units.
3. Unknown pricing stops the call instead of treating it as free.
4. Workflow, stage, provider and daily limits are checked before the worker handler runs.
5. Premium or high-cost requests can require operator review before execution.
6. On success, the service records one provider-call row and one cost-entry row.
7. Cost entries roll up to workflow and stage actual costs.
8. Reconciliation compares provider-call totals, cost-entry totals and workflow actual cost.

## Guarantees

- Budget stops happen before handler/provider execution.
- Budget stops write machine-readable workflow events.
- Duplicate completed worker results are reused and do not create a second billable row.
- Cost entries are append-only.
- Unknown pricing is blocked.
- Provider metadata is filtered before persistence by the application service.

## Reference pricing profiles

The first deterministic profiles cover:

- OpenAI image standard/premium;
- ElevenLabs voice standard;
- SerpAPI search standard.

These profiles are local test/reference profiles only. Production profiles should be reviewed before enabling real provider calls.
