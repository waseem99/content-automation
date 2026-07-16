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

## Temporal and multimodal report checkpoint

P75-04 adds a deterministic, hash-resumable timeline for processed video references. A normal
`refintel process` run writes `analysis/temporal_report.json` using schema
`p75.temporal_report.v1` and an offline `reports/temporal.html` review surface. Rebuild or open
that report without reprocessing the source:

```bash
refintel temporal-report <reference-id> --open-browser
```

The timeline keeps evidence types separate:

- every-frame samples supply measured motion, brightness, static ratios, and cut candidates;
- WAV windows supply measured RMS energy, silence candidates, and peak candidates;
- transcript segments and word timestamps supply spoken pacing and caption timing;
- OCR supplies extracted on-screen text cues with frame timestamps;
- local vision supplies labeled model observations, never measured facts.

Fixed-duration windows aggregate those signals into evidence-backed candidates for hook,
setup, development, payoff, CTA, pacing, editing profile, engagement mechanics, and production
difficulty. A corrupt OCR frame is isolated while the remaining timeline continues. A matching
input digest reuses the prior report unless `--force` is supplied.

The report must not claim that a still image or slideshow is moving video. `actual motion` is
confirmed only from every-frame measurements; a static ratio of 90% or more is labeled
`still_or_slideshow_like`. Missing every-frame data, audio, transcript, OCR, or model payoff is
listed as a limitation and changes the report status to `partial` where appropriate.

This checkpoint creates no production media and performs no publication or deployment. Source
media and source wording remain blocked from generated content, transferable mechanics are
abstracted for original work only, and human review remains mandatory.

## Cross-reference, clustering, originality, and rights checkpoint

P75-05 compares at least two processed `reference_fingerprint.json` files locally. It does not
compare or export source frames. The deterministic similarity model uses hook family, structural
story stages, pacing measurements, controlled visual/audio/mechanics terms, brand, format, and
platform. Source-specific free text is excluded from cluster features.

```bash
refintel compare-library \
  /absolute/path/ref-a/exports/reference_fingerprint.json \
  /absolute/path/ref-b/exports/reference_fingerprint.json \
  --output-dir /absolute/path/comparisons/portfolio-july \
  --metadata-file /absolute/path/comparison-metadata.json \
  --brand animal-x \
  --target-format facebook_reel \
  --topic "A separately researched original topic"
```

The optional metadata object is keyed by reference ID and may contain `brand_id` and
`format_name`. Without it, brand remains `unassigned` and format is inferred from orientation and
duration. The input digest includes fingerprints, project rights declarations, transcripts,
metadata, and clustering parameters, so any relevant change invalidates reuse.

Outputs are local and typed:

- `comparison_report.json` — profiles, pairwise evidence, clusters, facets, failures, and gates;
- `pattern_library.json` — mechanics supported by at least two references;
- `pattern_brief.json` — an original, multi-reference draft when rights and evidence permit;
- `originality_gate.json` — transcript/title overlap checks without persisted source excerpts;
- `index.html` — offline human-review surface.

Every valid declaration permits internal comparison only. Source-asset and production use remain
false until separate asset-level clearance and human approval. A missing declaration blocks the
run from readiness. A missing transcript never becomes an originality pass; it is reported as an
unmeasured limitation. Any invalid fingerprint is isolated with the supported authorized
`ingest-file` fallback.

Pattern briefs prohibit source footage, scripts, identities, likenesses, logos, watermarks,
voices, music, sound recordings, characters, shot order, composition, and branding. The gate
requires a new concept, wording, assets, setting, sequence, voice, and music treatment. It does
not generate, render, approve, publish, or deploy content automatically.

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
- Acquisition alone does not publish, deploy, analyze similarity, or send media to paid providers.

## Reusable CLI, skill, and acceptance checkpoint

P75-07 completes the reusable operator surface. `refintel run-reference` executes one authorized
input, while `refintel run-portfolio` validates a typed request and isolates every item failure.
The `cpu`, `gpu`, and `low-memory` profiles disclose their speech, vision, and every-frame choices
instead of silently changing evidence quality. Every successful item creates a sanitized portfolio
sync packet; every failure names an authorized local-upload fallback.

The repository packages `skills/analyze-social-references`, the deterministic seven-route matrix
at `reference-engine/pilots/p75-cross-platform-acceptance.json`, offline fixtures, and the complete
operator runbook at `docs/operations/p75-reference-intelligence-runbook.md`. The existing P67
workflow remains the controlled Facebook public probe. Other platforms remain honestly conditional
until an operator supplies a suitable authorized reference.

This checkpoint introduces no Vercel media processing, automatic approval, generation, rendering,
or publication.

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
