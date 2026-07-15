# P71 Portfolio staging runbook

This phase creates a local/private staging runtime only. It does not deploy Vercel,
apply migrations to production, call paid models, or publish content.

## Configure

1. Copy `deploy/portfolio-staging/.env.example` to `deploy/portfolio-staging/.env`.
2. Replace both placeholder secrets with different long random values.
3. Set `OPERATOR_CORS_ORIGINS` to the exact dashboard origin. Never use `*`.
4. Replace onboarding placeholders and add verified page links in
   `config/portfolio-brands.staging.json` before content research begins.

## Start and migrate once

```bash
docker compose --env-file deploy/portfolio-staging/.env \
  -f deploy/portfolio-staging/compose.yaml up --build -d
```

The database is password protected and bound to localhost. The one-shot migration service
must complete successfully before the operator API starts. The API is also localhost-bound
by default and refuses protected routes without an operator key.

## Onboard brands and plans

```bash
set -a
. deploy/portfolio-staging/.env
set +a
python scripts/p71_bootstrap_portfolio.py
python scripts/p71_smoke_portfolio.py
```

Secrets are read from environment variables and never written to the brand configuration.
The bootstrap is idempotent for brands, month plans, and the confirmed-brand idea inventory.
See `docs/operations/p72-month-inventory.md` for the readiness contract and review gate.

## Dashboard

Open the static dashboard, choose **Connect Data**, enter the staging API URL and operator
key, and verify the database item count. The key stays in browser session storage.

## Promotion gate

Do not create a Vercel preview until migrations, readiness, authentication, brand counts,
queue reads, and approval transitions pass in staging. Do not promote placeholders as live
brands. Publishing remains manual and outside this staging stack.
