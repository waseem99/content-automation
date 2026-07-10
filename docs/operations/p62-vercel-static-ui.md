# P62 Vercel-Deployable Static Creator UI

Part of #667. P63 adds the Vercel deployment lock after Vercel auto-detected the Python/FastAPI code in `src/` when the repo root was used as the Vercel project root.

## What this builds

P62 adds a static browser app that can be deployed on Vercel without a hosted backend, serverless API, server-side AI call, Python runtime in the browser, external scripts, or API keys.

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
web/static-creator-ui/vercel.json
scripts/build-static-creator-ui.js
package.json
vercel.json
tests/integration/test_p62_vercel_static_ui.py
```

## Why the P63 hotfix exists

The repository also contains Python CLI/API code with variables named `app`. If Vercel is pointed at the repository root, Vercel may scan the whole repo and try to deploy it as a FastAPI project, causing this error:

```text
No FastAPI entrypoint found in default locations, but found potential entrypoints
```

The safest deployment contract is therefore:

```text
Vercel Root Directory: web/static-creator-ui
```

That keeps Vercel inside the deployable static app folder and outside the Python project files.

## Recommended Vercel deploy path

Use the static UI folder as the Vercel project root.

Recommended Vercel settings:

```text
Framework Preset: Other
Root Directory: web/static-creator-ui
Build Command: leave empty
Output Directory: leave empty
Install Command: leave empty
```

The nested `web/static-creator-ui/vercel.json` handles these routes:

```text
/      -> static creator UI
/app   -> static creator UI
/assets/app.js -> local browser JS
/assets/styles.css -> local CSS
/sample-brief.json -> sample brief
/wordpress-embed.html -> secondary embed snippet
```

## Repo-root fallback

A root `package.json`, root `vercel.json`, and `scripts/build-static-creator-ui.js` also exist as a fallback static build contract:

```text
npm run build
```

That command copies:

```text
web/static-creator-ui/
```

into:

```text
dist/
```

However, because Vercel already detected FastAPI before running the build in this mixed Python repository, the recommended production setup is still to set Root Directory to:

```text
web/static-creator-ui
```

## Local smoke test

Open this file directly in a browser:

```text
web/static-creator-ui/index.html
```

Or run the fallback static build locally:

```bash
npm run build
```

Then open:

```text
dist/index.html
```

## Important product position

This is a deployable static MVP UI. It does not yet run the Python P40–P61 pipeline in the browser and it does not call a server-side AI model. Instead, it provides a deterministic, browser-only first-pass content planning pack so the workflow can be tested on Vercel without backend setup.

## Guardrails

P62/P63 do not:

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
