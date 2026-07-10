# P62 Vercel-Deployable Static Creator UI

Part of #667. P63 adds the Vercel static build lock after Vercel auto-detected the Python/FastAPI code in `src/`.

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
scripts/build-static-creator-ui.js
package.json
vercel.json
tests/integration/test_p62_vercel_static_ui.py
```

## Why the P63 hotfix exists

The repository also contains Python CLI/API code with variables named `app`. Vercel originally scanned the whole repo and tried to deploy it as a FastAPI project, which caused this error:

```text
No FastAPI entrypoint found in default locations, but found potential entrypoints
```

P63 fixes this by adding a minimal Node static build contract:

```text
npm run build
```

That command copies the browser-only app from:

```text
web/static-creator-ui/
```

into:

```text
dist/
```

Vercel then serves only the static `dist/` output.

## Vercel deploy path

Use the repo root as the Vercel project root.

Recommended Vercel settings:

```text
Framework Preset: Other
Build Command: npm run build
Output Directory: dist
Install Command: leave empty or let vercel.json use the no-install command
Root Directory: repository root
```

The root `vercel.json` now defines:

```text
installCommand: node -e "console.log('No install required for static Creator UI')"
buildCommand: npm run build
outputDirectory: dist
```

After deployment:

```text
/      -> static creator UI
/app   -> static creator UI
/assets/app.js -> local browser JS
/assets/styles.css -> local CSS
/sample-brief.json -> sample brief
```

## Local smoke test

Run:

```bash
npm run build
```

Then open:

```text
dist/index.html
```

You can also open the source file directly for quick local inspection:

```text
web/static-creator-ui/index.html
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
