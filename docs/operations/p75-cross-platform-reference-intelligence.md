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

## Next implementation slices

The adapter contract unblocks the remaining P75 issues: platform acquisition implementations, image/carousel processing, multimodal reports, cross-reference clustering and originality gates, operator UI/API integration, and the full offline acceptance pack.
