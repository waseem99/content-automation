# P69 Multi-brand portfolio content engine

## Purpose

Operate six video brands and one mixed news brand from a rolling 30-day queue while
preserving originality, human approvals, provider lineage, rights checks, and spend control.

## Runtime boundary

- PostgreSQL is the source of truth. Apply `0026_portfolio_content_engine.sql` once in the
  target environment through the existing migration runner.
- The operator API exposes brand upsert, month-plan creation, filtered queue, duplicate-safe
  content creation, staged approvals, platform packaging, and analytics observation endpoints.
- The Vercel surface stays static. Do not deploy it repeatedly during implementation.
- No endpoint publishes to Facebook, YouTube, TikTok, or Instagram.

## Approval sequence

`idea → script → preview → premium_spend → package → publish`

Each approved gate advances exactly one stage. Changes requested retain the current stage;
rejection blocks the content item. Premium generation therefore cannot be treated as implied
approval merely because a preview exists.

## Duplicate and reuse policy

- Exact concept fingerprints are brand-scoped and include the content format.
- Semantic keys catch simple cross-plan restatements before insert.
- Reusable clips must reference registered assets, have an explicit reuse scope, and carry
  maximum-use counts. Reuse is optional and never replaces originality review.

## Analytics policy

Analytics are append-only observations. Early retention problems change hooks first; weak
completion changes pacing; strong share signals can justify selectively expanding a pillar.
No metric automatically approves, publishes, or increases cadence.

## Minimal deployment procedure

1. Run unit/integration checks locally.
2. Build the static UI once.
3. Apply the database migration once in staging and smoke-test the four portfolio endpoints.
4. Produce one Vercel preview deployment only if a remote stakeholder must review it.
5. Promote the already-reviewed artifact once; do not create a deployment per code change.
