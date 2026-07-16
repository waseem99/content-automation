# P79 four-brand month factory

P79 turns the four confirmed Facebook brands into one factual production-control manifest.
It starts no paid render, publish job, platform login, or Vercel deployment.

## Current operating state

- Rawr Nation: 24 of 24 August concepts ready.
- Animal X: 24 of 24 August concepts ready.
- Historiq: account brief and reference review required before concepts are generated.
- Ani Films: account brief and reference review required before concepts are generated.

The 48 existing concepts are divided into batches of six. Existing P68 pilot packs,
narrations, and previews are detected and surfaced at their actual stage. A concept is not
described as production-ready merely because its title exists.

## Rebuild the control manifest

Run this after adding a brand brief, concept inventory, pilot pack, narration, or preview:

```bash
python scripts/p79_build_month_factory.py
npm run build
```

The command writes `web/static-creator-ui/data/month-factory.json`. The static Creator UI
loads this file instead of its illustrative demo rows, showing the four priority brands,
48 current concepts, six-item batch assignments, detected production assets, and missing
briefs. Connecting the local operator API still replaces this read-only seed with persistent
database state and the full approval workflow.

## Execution order

1. Review Rawr Nation batch 1 concepts and sources.
2. Generate and approve six script/storyboard/voice packs.
3. Generate local Kokoro narration and free motion previews.
4. Approve concepts, story, narration, and pacing in the operator UI.
5. Set a per-video premium budget and generate only approved realism-critical shots.
6. Assemble final masters and create Facebook, YouTube Shorts, and TikTok packages.
7. Repeat for batches 2–4, then Animal X.
8. Add Historiq and Ani Films only after their account briefs and reference analysis are
   recorded; do not invent their content strategy from a page identifier.

## Refresh after local database startup

```bash
set -a
. deploy/portfolio-staging/.env
set +a
python scripts/p71_bootstrap_portfolio.py
python scripts/p76_local_production_doctor.py
```

Use `scripts/p76_sync_pilot.py` to attach a matching local pilot to its database content
item. The editorial-match confirmation remains mandatory. Human approval is required before
paid generation and again before publishing.

## Inputs still required from the owner

For Historiq and Ani Films, record the target audience, language, geography, preferred and
prohibited topics, desired tone, typical duration, existing high performers, monetization
constraints, and any visual identity rules. Facebook credentials are not required to build
Rawr Nation and Animal X batches locally.
