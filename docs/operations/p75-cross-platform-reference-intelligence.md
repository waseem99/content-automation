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

## Image and carousel checkpoint

P75-03 adds typed, local-first processing for one image, a thumbnail, or an ordered image
folder. It deliberately separates:

- deterministic measurements such as dimensions, palette, luminance, contrast, saturation,
  entropy, edge density, and visual center;
- extracted OCR text, boxes, confidence, coverage, hierarchy zones, and generic CTA terms;
- optional local-model observations about generic subjects, layout, hierarchy, and likely
  narrative role;
- unavailable evidence and per-item failures.

```bash
cd reference-engine
refintel process-images /absolute/path/authorized-carousel \
  --rights public-internal-research
```

Use `--local-vision` only when the configured Ollama model is running locally. A model failure
is isolated to that slide and cannot convert an observation into a measured fact. A corrupt
slide is recorded with a local-export fallback while readable slides continue. Re-running an
unchanged folder reuses the SHA-256-matched manifest; `--force` rebuilds it.

Outputs remain under `workspace/image-references/<reference-id>/` and include:

- normalized source copies retained only in the reference workspace;
- `image-reference.json` using `p75.image_reference.v1`;
- `analysis-summary.json`;
- `contact-sheet.jpg` when at least one slide succeeds.

Opening, setup, development, payoff/close, and CTA labels are sequence candidates rather than
claims about creator intent. Source text must not be reused verbatim, source imagery must not
enter generated content, and human review is required before any brief or production action.

### Environment-based local authorization

The CLI accepts safe environment defaults for `REFINTEL_WORKSPACE`,
`REFINTEL_FACEBOOK_PROFILE`, `REFINTEL_FACEBOOK_COOKIE_FILE`, and
`REFINTEL_COOKIES_FROM_BROWSER`. Cookie variables contain a local path or supported browser
name only—never raw cookies, passwords, MFA values, or session tokens. Explicit CLI auth flags
take precedence. Conflicting cookie-file/browser routes fail closed.

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

The completed adapter, acquisition, and image/carousel contracts now unblock temporal and
multimodal reports, cross-reference clustering and originality gates, operator UI/API
integration, and the full offline acceptance pack.
