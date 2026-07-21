# P98 Performance Analytics Contract

P98 is an append-only learning and production-economics layer over exact successful P97 deliveries and immutable P96 release packages.

## Evidence boundary

- Imports use a caller-provided idempotency key and a SHA-256 digest of the complete normalized request.
- Every observation binds one exact successful delivery request, platform reference, approved release, content version, brand, platform, and observation window.
- The existing legacy `performance_observations` table remains unchanged. P98 writes normalized delivery evidence to `performance_delivery_observations`.
- Imported observations, experiment results, and recommendations are append-only.
- Source account references are identifiers only and must not contain credentials or secret material.

## Creative lineage

Creative dimensions are derived from production records rather than accepted from the import payload. Each observation retains:

- concept text, fingerprint, and semantic key;
- declared content pillar and its source, or `unclassified` when no pillar was declared;
- approved script hook and format;
- final audio duration and exact narration preset;
- brand profile and approved visual-preset/style snapshots;
- routed renderer providers/models where applicable;
- the exact P87 final-assembly provider/model;
- final release, delivery request, and target identity.

## Production economics

`production_cost_usd` must equal the immutable final-release cost plus reconciled managed-render spend. Derived read models expose:

- cost per item;
- cost per thousand normalized views;
- revenue per thousand normalized views;
- contribution after production cost.

Zero-view observations retain null per-thousand economics rather than fabricated denominators.

## Controlled experiments

Experiments declare variants, a winner metric and direction, minimum observations, minimum normalized views, and a minimum relative difference before activation. Multiple delivery variants may intentionally reuse one approved release when testing copy, thumbnail, privacy, or timing.

Evaluations distinguish:

- `insufficient_data`: declared sample or view thresholds are not met, including zero-observation evaluations;
- `meaningful_result`: every declared threshold passes and the winning variant belongs to the experiment;
- `no_winner`: evidence is sufficient but the declared winner threshold is not met.

The retained `significance_threshold` is configuration evidence. P98 does not claim that a statistical significance test was applied; evaluation summaries state this explicitly.

## Advisory-only learning

Recommendations must cite existing same-brand observations and metric evidence. They remain advisory and cannot approve content, mutate a production workflow, schedule delivery, or publish a post. Admins configure imports and experiments, Reviewers evaluate evidence and record recommendations, and brand-scoped operators have read-only analytics access.

## Validation

The dedicated P98 PostgreSQL workflow applies the complete migration chain and runs:

- model and migration contract tests;
- idempotent import and economics lifecycle tests;
- insufficient-data, meaningful-result, and no-winner experiment tests;
- append-only recommendation tests;
- configured API role and brand-scope tests;
- P97 delivery lifecycle compatibility tests.

No external analytics API, live publication, paid provider, or deployment is used by the P98 CI path.
