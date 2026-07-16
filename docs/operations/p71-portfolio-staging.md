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

Serve the dashboard locally from the repository root:

```bash
python -m http.server 3000 --directory web/static-creator-ui
```

Open `http://127.0.0.1:3000`, choose **Connect Data**, enter
`http://127.0.0.1:8000` and the operator key, and verify the database item count. The key
stays in browser session storage. Choose **Rawr Nation**, then open a queue item to review
and version its script, scene plan, voice metadata, local narration/preview media, approval
prerequisites, and decision history.

## Attach locally generated review media

Place generated files beneath `PORTFOLIO_MEDIA_DIR`. The default is
`var/portfolio-media` in the repository. Keep the same relative path in a `content://`
locator, compute its SHA-256 digest, then register metadata through the protected operator
API. For example, a file stored at:

```text
var/portfolio-media/rawr-nation/<content-id>/preview-v1.mp4
```

uses this locator:

```text
content://rawr-nation/<content-id>/preview-v1.mp4
```

Register both a `voiceover` artifact and a `preview` artifact before the preview gate can
be approved. The API container mounts this directory read-only. It does not accept browser
uploads, expose arbitrary filesystem paths, or copy generated media to Vercel.

The workspace stages enforce these minimum review artifacts:

- Script approval requires saved script and scene-plan JSON.
- Preview approval requires registered voiceover and preview media.
- Premium-spend approval requires an explicit USD budget, including zero when no paid shot
  is needed.
- Package approval requires a final video or retained preview.

**Request changes** records the rationale and opens a new content version. Approval never
starts generation, spends provider credits, or publishes content.

## Promotion gate

Do not create a Vercel preview until migrations, readiness, authentication, brand counts,
queue reads, and approval transitions pass in staging. Do not promote placeholders as live
brands. Publishing remains manual and outside this staging stack.
