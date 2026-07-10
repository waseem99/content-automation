# P62 Vercel-Deployable Static Creator UI

Part of #667. P63 adds the Vercel deployment lock after Vercel repeatedly auto-detected the Python/FastAPI project instead of the static Creator UI.

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
.vercelignore
scripts/build-static-creator-ui.js
package.json
vercel.json
tests/integration/test_p62_vercel_static_ui.py
```

## Why the P63 hotfix exists

The repository contains Python CLI/API code with variables named `app`. The Vercel project was saved with the FastAPI Framework Preset, so Vercel kept trying to locate a FastAPI entrypoint even after Python files were excluded.

The repo now overrides the saved framework setting in both Vercel configuration files:

```text
framework: null
```

In Vercel, `framework: null` explicitly selects **Other** for that deployment and overrides the project-level FastAPI preset.

The root config also uses:

```text
installCommand: ""
buildCommand: npm run build
outputDirectory: dist
```

The build command copies the browser-only source from:

```text
web/static-creator-ui/
```

into:

```text
dist/
```

The root `.vercelignore` excludes Python/FastAPI files from the deployment context, including:

```text
src/
tests/
pyproject.toml
requirements.txt
setup.py
```

## Recommended Vercel settings

The repository config should now override the previously saved FastAPI preset automatically.

Use:

```text
Framework Preset: Other
Build Command: npm run build
Output Directory: dist
Install Command: leave empty
```

If using a new project or if Root Directory is available, the clean static-only setup is:

```text
Root Directory: web/static-creator-ui
Framework Preset: Other
Build Command: leave empty
Output Directory: .
Install Command: leave empty
```

The nested `web/static-creator-ui/vercel.json` also contains `framework: null` and serves the static folder directly.

## Routes

```text
/      -> static creator UI
/app   -> static creator UI
/assets/app.js -> local browser JS
/assets/styles.css -> local CSS
/sample-brief.json -> sample brief
/wordpress-embed.html -> secondary embed snippet
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

You can also open the source directly:

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
