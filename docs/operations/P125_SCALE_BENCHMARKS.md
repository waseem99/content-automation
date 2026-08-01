# P125 Database Scale Benchmarks

## Purpose

P125 measures whether the PostgreSQL control plane can retain and operate the campaign and orchestration volume required before final video generation is connected.

It does **not** measure or claim final-video rendering throughput, GPU capacity, visual quality, publishing throughput, or provider cost.

## Default full benchmark

```powershell
python -m src.operations.scale_benchmark `
  --items 10000 `
  --checks-per-run 100 `
  --claim-sample 500 `
  --actor local-admin
```

This produces and verifies:

- 10,000 canonical campaign items;
- 10,000 durable pre-generation runs;
- 1,000,000 retained check records;
- a complete replay of the item set without duplicate item rows;
- a complete replay of retained checks without duplicate check rows;
- a 500-run PostgreSQL `SKIP LOCKED` claim sample;
- exact timings and counters stored in `football_brief.scale_benchmark_runs`.

## Staged execution

| Stage | Items | Checks per run | Total checks | Purpose |
|---|---:|---:|---:|---|
| Smoke | 100 | 5 | 500 | Local functional verification |
| CI | 1,000 | 10 | 10,000 | Pull-request regression gate |
| Medium | 5,000 | 50 | 250,000 | Workstation/database tuning |
| Target | 10,000 | 100 | 1,000,000 | Central-ecosystem acceptance |
| Upper bound | 20,000 | 100 | 2,000,000 | Future operational headroom |

## Passing conditions

A run passes only when:

1. retained campaign-item count equals the requested item count;
2. retained pre-generation-run count equals the requested item count;
3. retained synthetic-check count equals `items × checks_per_run`;
4. no additional check rows are inserted during the idempotent replay;
5. campaign validation reports zero invalid items;
6. the requested claim sample is successfully leased and safely released;
7. the evidence row explicitly records that final video generation was not measured.

## Interpretation

A passing 10,000-item run means the database-native campaign and orchestration layer can retain that control-plane workload under the measured environment. It does not mean the system can render 10,000 finished videos in the same elapsed time.

Hybrid rendering capacity must be benchmarked separately after renderer routing, GPU fleet capacity, retry rates, accepted-second cost, and visual-quality gates are implemented.

## Evidence

Every execution writes an immutable operational record containing:

- benchmark key;
- campaign ID;
- requested and inserted counts;
- duplicate counts;
- claim sample;
- per-stage timings;
- environment and Git SHA;
- pass/fail status and error evidence.

Do not delete successful target-scale evidence during ordinary cleanup.
