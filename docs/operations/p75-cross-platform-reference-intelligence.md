# P75 cross-platform reference intelligence

P75 turns authorized public social links and local media into normalized evidence for the existing reference-analysis pipeline. The first checkpoint establishes a canonical adapter contract for YouTube and Shorts, Instagram, TikTok, X/Twitter, Facebook, and Snapchat.

## Product boundary

The engine processes media the operator owns, is permitted to use, or may lawfully inspect as a public reference. It does not bypass private-account controls, DRM, paywalls, CAPTCHAs, platform safeguards, or rate limits. Authentication remains inside an operator-controlled local browser profile, and credentials or session files must never enter logs, reports, commits, or hosted services.

Reverse engineering means identifying transferable creative mechanics: hook timing, story structure, shot grammar, pacing, narration, text density, sound design, emotion, reveal, payoff, and CTA. It does not mean copying scripts, characters, compositions, source assets, or other source-specific expression. Every production brief remains draft-only until human review and originality checks pass.

## Capability labels

- `supported`: an offline-tested route is implemented for the recognized input shape.
- `conditional`: the route exists but depends on public availability, extractor behavior, authorization, or site behavior.
- `unsupported`: the operator must supply an authorized local export.

Platform recognition is not a promise that a URL can be downloaded. `plan-url` classifies and normalizes without acquiring anything, while `capabilities` reports the honest adapter matrix.

```bash
cd reference-engine
refintel capabilities
refintel capabilities --json
refintel plan-url \
  'https://www.youtube.com/shorts/VIDEO_ID' \
  'https://www.facebook.com/RawrNationTV' \
  'https://www.snapchat.com/spotlight/PUBLIC_ID'
```

## Canonical input contract

Each planned reference records the original URL, canonical URL, platform, input type, likely media kind, support level, acquisition route, stable media ID when visible, redirect requirement, and limitations.

Ordinary tracking parameters and fragments are removed. Identity-bearing query parameters are retained, which prevents two YouTube `watch?v=` links from collapsing into the same library record. Twitter hosts normalize to `x.com` while media identifiers remain intact.

## Current routes

| Platform | Direct media | Profile/page | Notes |
|---|---|---|---|
| YouTube / Shorts | extractor | discover then extract | Public watch, Shorts, live, and short URLs are recognized |
| Instagram | extractor, then authorized local browser | conditional discovery | Posts may be video, image, or carousel |
| TikTok | extractor | conditional discovery | Video and photo routes are distinguished |
| X / Twitter | extractor | conditional discovery | A status may contain mixed or multiple assets |
| Facebook | extractor | local Playwright discovery | Share links are resolved before classification |
| Snapchat | verify, then local-file fallback | local-file fallback | Spotlight and Story support remains experimental |

## Operator sequence

1. Record the rights declaration and keep any authorization note free of secrets.
2. Run `plan-url` on every supplied URL.
3. Resolve share redirects and discover direct candidates from profile/page inputs.
4. Acquire each candidate independently and persist provenance, hashes, and failures.
5. Run deterministic video/image/carousel measurements before model interpretation.
6. Produce temporal or carousel maps, evidence-backed observations, and fingerprints.
7. Generate an originality-safe brief and require human approval before production.

## Acquisition checkpoint

P75-02 adds a resumable acquisition layer beneath `ingest-url`. Every attempt writes
`source/acquisition-manifest.json` before download begins and updates it on success or
failure. The manifest contains the normalized reference, rights declaration, route,
attempt count, allowlisted source metadata, primary asset, cryptographic hashes, asset
inventory, sanitized diagnostics, and the supported local-file fallback. Cookie values,
cookie paths, authorization parameters, signed query values, and raw extractor URLs are
not persisted.

Downloads use bounded retries, partial-file continuation, one fragment at a time, request
sleeping, an optional rate limit, and a per-reference download archive. A completed asset
is reused only when its stored SHA-256 still matches; invalid resume state is quarantined
inside the local reference workspace before retry.

Plan and acquire independent direct links:

```bash
refintel plan-url '<direct-url-1>' '<direct-url-2>'
refintel acquire-batch '<direct-url-1>' '<direct-url-2>' \
  --rights public-internal-research
```

Discover public candidates without downloading them:

```bash
refintel discover-url 'https://www.youtube.com/@channel' --limit 20
```

Facebook page discovery remains on the dedicated local Playwright profile. After the
operator completes the one-time login, acquire references for all four configured brands
without analysis:

```bash
refintel facebook-login
python scripts/p74_run_facebook_portfolio.py \
  --rights public-internal-research \
  --limit 6 \
  --acquire-only
```

Run the same command without `--acquire-only` only after reviewing acquisition manifests;
that proceeds into every-frame, transcript, sequence, report, and fingerprint processing.

### Current acquisition limits

- YouTube/Shorts direct URLs are the strongest public extractor route; channel discovery
  remains conditional on public visibility.
- Facebook direct videos use the extractor, while page discovery uses the dedicated local
  browser profile. Share redirects must first resolve to stable page or media URLs.
- Instagram, TikTok, and X direct public routes remain conditional and can require an
  operator-owned local browser session or authorized local export.
- Snapchat Spotlight/Story acquisition is experimental. Snapchat profile discovery is not
  claimed; an authorized local export is the dependable fallback.
- Acquisition does not publish, deploy, analyze similarity, or send media to paid providers.

## Next implementation slices

The completed adapter, acquisition, image/carousel, temporal-report, comparison/gate, and
portfolio-integration contracts now unblock the reusable CLI skill and full offline acceptance
pack.

## Portfolio API and operator UI checkpoint

P75-06 connects local reference research to the database-backed portfolio without moving source
media into PostgreSQL, the API, or Vercel. Migration `0027_reference_intelligence_portfolio.sql`
adds source queues, resumable local-worker jobs, review-artifact pointers, brand assignments,
append-only human gates, and traceable research-to-idea links.

Create a sanitized handoff packet after processing a local reference:

```bash
refintel portfolio-sync-packet <reference-id>
```

The packet includes a sanitized public locator, locator hash, job status, progress, artifact
fingerprints, limitations, and pending human gates. It includes no source bytes, absolute local
paths, cookies, credentials, automatic generation decision, or publication instruction. The
operator API accepts that metadata through `/portfolio/references` and related job, artifact,
brand, approval, and idea-link endpoints. Heavy processing remains an operator-controlled local
worker responsibility.

The static portfolio UI can list and filter the queue, inspect artifact and gate state, and record
explicit rights, originality, and editorial decisions. An approval is audit evidence only: it
does not render or publish content. Linking research to an idea additionally requires approved
rights and originality gates plus a written transformation note.
