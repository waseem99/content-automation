# P62 Vercel-Deployable Static Creator UI

Part of #667. Closes #668–#673 after merge.

## What this builds

P62 adds a static browser app that can be deployed on Vercel without Python, backend APIs, npm install, serverless functions, external scripts, or API keys.

The app lets a user:

1. Draft a video content brief.
2. Generate a first-pass review pack in the browser.
3. Review hook, title options, script, storyboard, rights notes, monetization notes, QA, and revision prompts.
4. Copy/download the brief JSON, review pack JSON, producer brief Markdown, script text, and QA checklist.

## Files

```text
web/static-creator-ui/index.html
web/static-creator-ui/assets/styles.css
web/static-creator-ui/assets/app.js
web/static-creator-ui/sample-brief.json
web/static-creator-ui/wordpress-embed.html
vercel.json
tests/integration/test_p62_vercel_static_ui.py
```

## Vercel deploy path

Use the repo root as the Vercel project root.

Recommended Vercel settings:

```text
Framework Preset: Other
Build Command: leave empty
Output Directory: leave empty
Install Command: leave empty
Root Directory: repository root
```

After deployment:

```text
/      -> static creator UI
/app   -> static creator UI
/assets/app.js -> local browser JS
/assets/styles.css -> local CSS
```

## Local smoke test

Open this file directly in a browser:

```text
web/static-creator-ui/index.html
```

Or serve the repo root using any static file server and open `/` if `vercel.json` is being respected by the host.

## Important product position

This is a deployable static MVP UI. It does not yet run the Python P40–P61 pipeline in the browser and it does not call a server-side AI model. Instead, it provides a deterministic, browser-only first-pass content planning pack so the workflow can be tested on Vercel without backend setup.

## Guardrails

P62 does not:

- create a hosted backend/API;
- require authentication;
- use a database;
- call external services;
- render or edit video;
- download assets;
- upload or publish content;
- approve content automatically;
- guarantee views, monetization, or performance.

Human review remains required before production.

## Secondary WordPress embed

After deploying to Vercel, copy `web/static-creator-ui/wordpress-embed.html` into a WordPress Custom HTML block and replace `YOUR-VERCEL-DOMAIN` with the Vercel domain.
