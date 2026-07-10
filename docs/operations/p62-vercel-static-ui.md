# P62 Vercel-Deployable Static Creator UI

Part of #667. P63 adds the Vercel deployment lock after Vercel repeatedly auto-detected the Python/FastAPI project instead of the static Creator UI.

## What this builds

P62 adds a static browser app that can be deployed on Vercel without a hosted backend, serverless API, server-side AI call, Python runtime in the browser, external scripts, or API keys.

The app now includes:

1. An interactive architecture map of the complete content engine.
2. Filters for engagement, policy and rights, and monetization responsibility.
3. Clickable stages showing modules, tools, outputs, implementation status, and decision gates.
4. Runtime lanes for the browser UI, local Python engine, human governance, and planned model integration.
5. A traceability loop from input brief through revision and before/after comparison.
6. A browser-based first-pass content pack generator with JSON and Markdown exports.

## Engine map stages

1. Brief Intake and Normalization — P59, P60, P61.
2. Content Package Generation — P40, P48, P49.
3. Engagement and Retention — P42, P50, P53.
4. Policy, Rights and Safety — P41, P50, P56.
5. Monetization Readiness — P44, P48, P49.
6. Production Handoff — P43, P46, P47.
7. Orchestration and Batch Operations — P45, P47, P58, P61.
8. Human Review and Revision — P50, P51, P52, P53, P56, P57.
9. Review Workspaces and Deployment — P54, P55, P62, P63.
10. Secure model generation layer — clearly marked as planned, not active.

Each stage exposes its exact code modules, runtime tools, generated artifacts, quality gate, primary objective responsibility, and secondary impact on all three objectives.

The three objective controls are:

- Engagement: hook, retention, pacing, platform format, creative QA.
- Policy and rights: sources, claims, copyright, likeness, licensed assets, human approval.
- Monetization: CTA, offer alignment, platform fit, and commercial readiness without outcome guarantees.

## Runtime boundaries

The deployed Vercel interface is static and browser-only. The deeper P40–P61 processing remains implemented as local Python modules and runners. Human review remains mandatory. External model generation is planned but not connected to this static deployment.

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

## Vercel framework override

The repository contains Python CLI and API code. To prevent Vercel from treating the project as FastAPI, both Vercel configuration files use:

```text
framework: null
```

The root config also uses:

```text
installCommand: ""
buildCommand: npm run build
outputDirectory: dist
```

The build command copies `web/static-creator-ui/` into `dist/`. The root `.vercelignore` excludes the Python project files from the deployment context.

## Recommended Vercel settings

```text
Framework Preset: Other
Build Command: npm run build
Output Directory: dist
Install Command: leave empty
```

For a clean static-only project:

```text
Root Directory: web/static-creator-ui
Framework Preset: Other
Build Command: leave empty
Output Directory: .
Install Command: leave empty
```

## Routes

```text
/      -> interactive engine map and static creator UI
/app   -> interactive engine map and static creator UI
/assets/app.js -> local browser JavaScript
/assets/styles.css -> local CSS
/sample-brief.json -> sample brief
/wordpress-embed.html -> secondary embed snippet
```

## Local smoke test

```bash
npm run build
```

Then open `dist/index.html`.

## Guardrails

The static deployment does not create a hosted backend, authentication, database, external model call, video renderer, asset downloader, automatic uploader, publisher, or final approval process. It does not guarantee views, monetization, conversions, or performance.

Human review remains required before production.
