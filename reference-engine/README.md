# Local Reference Intelligence Engine

This package ingests authorized social-video, image, thumbnail, and carousel references or
local files, decomposes them into measurable evidence, and exports originality-safe inputs for
the existing content workflow.

## Product boundaries

- Local-first. No paid per-video API is required.
- Use only media you own, have permission to analyze, or may lawfully use for internal research.
- No DRM bypass, paywall bypass, private-account circumvention, CAPTCHA evasion, or access-control bypass.
- Browser cookies remain local and are never logged or committed.
- Source media is not copied into generated production packages.
- The engine extracts creative mechanics; it does not reproduce exact scripts, shots, branding, music, voices, characters, watermarks, or proprietary artwork.
- Human review is required before an exported brief or render is used.

## Architecture

```text
URL, local video, image, or carousel folder
  -> rights declaration
  -> local ingestion / yt-dlp
  -> FFmpeg normalization + ffprobe metadata
  -> fixed-interval frames + scene keyframes + contact sheet
  -> local transcript and caption timing
  -> hook/story/pacing/style analysis
  -> offline interactive HTML report
  -> reference_fingerprint.json
  -> original_content_brief.json
  -> P40-P61 review workflow
  -> P65 renderer
```

## Minimum setup

- Python 3.11+
- FFmpeg and ffprobe available on PATH
- 8 GB RAM for media processing
- Optional GPU for faster-whisper and local vision models

```bash
cd reference-engine
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[media,dev]'
refintel doctor
```

For local transcription:

```bash
pip install -e '.[media,speech,dev]'
```

For all optional capabilities:

```bash
pip install -e '.[all,dev]'
playwright install chromium
```

## First local-file run

```bash
refintel ingest-file /absolute/path/reference.mp4 \
  --rights public-internal-research \
  --title "Reference sample"

refintel process <reference-id>
refintel report <reference-id> --open-browser
refintel export-brief <reference-id> --brand rawr_nation
```

The workspace is stored under `reference-engine/workspace/` by default.

## Image, thumbnail, and carousel analysis

Analyze one image or an ordered local folder. Filenames are naturally ordered, so `slide-2`
precedes `slide-10`:

```bash
refintel process-images /absolute/path/carousel-folder \
  --rights public-internal-research \
  --title "Authorized carousel"
```

The local run produces a typed `p75.image_reference.v1` manifest, SHA-256 provenance,
dimensions, orientation, palette, brightness, contrast, saturation, entropy, edge density,
visual center, OCR regions and confidence when Tesseract is available, ordered sequence-role
candidates, per-slide failures, and a contact sheet. Add `--local-vision` to obtain explicitly
labeled local-model observations for generic subjects, layout, hierarchy, and narrative role.

Sequence roles are candidates, not asserted story facts. Source text and source imagery are
blocked from verbatim reuse, and human review remains mandatory.

## Local environment configuration

Copy `.env.example` values into your private shell or secret manager. Environment values are
read directly; the CLI does not parse or upload `.env` files.

```bash
export REFINTEL_WORKSPACE="$PWD/workspace"
export REFINTEL_FACEBOOK_PROFILE="$HOME/.local/share/refintel/facebook-browser"
export REFINTEL_FACEBOOK_COOKIE_FILE="$REFINTEL_FACEBOOK_PROFILE/facebook-cookies.txt"
```

Store only paths in these variables, never Facebook email/password values or raw cookie
contents. Explicit CLI authentication flags override environment defaults. Media processing
remains on the local/private worker and is excluded from Vercel.

## Authorized URL ingestion

Inspect cross-platform support or normalize inputs without downloading:

```bash
refintel capabilities
refintel capabilities --json
refintel plan-url 'https://www.youtube.com/shorts/VIDEO_ID'
refintel acquire-batch '<direct-url-1>' '<direct-url-2>' \
  --rights public-internal-research
refintel discover-url 'https://www.youtube.com/@channel' --limit 20
```

The planner covers YouTube/Shorts, Instagram, TikTok, X/Twitter, Facebook, and
Snapchat. It labels conditional routes honestly and preserves identity-bearing
query parameters while removing ordinary tracking parameters.

```bash
refintel ingest-url 'https://www.youtube.com/watch?v=...' \
  --rights permitted \
  --title "Authorized reference"
```

Use a direct reel/video/post URL, not a platform profile, channel, or home page.
Supported direct-input contracts cover Facebook, Instagram, YouTube, TikTok, X,
and conditional public Snapchat Spotlight/Story inputs.
If an extractor cannot access an otherwise authorized video, download it through
the platform's permitted/operator-owned route and use `ingest-file`.

For an operator-owned session, cookies can be read locally by yt-dlp:

```bash
refintel ingest-url '<url>' \
  --rights owned \
  --cookies-from-browser chrome
```

The engine never uploads cookies or includes them in logs. If a platform extractor cannot
access a video, use `ingest-file` as the supported fallback.

Every URL attempt writes a sanitized, resumable
`source/acquisition-manifest.json` with asset hashes, allowlisted metadata, retry status,
and a local-file fallback. Use `--acquire-only` with `facebook-page` to download and review
references before running frame, transcript, and storytelling analysis.

## Facebook page batch ingestion

P74 adds a dedicated Playwright profile for authorized Facebook page discovery, followed by
yt-dlp download and the existing local analysis pipeline. See
`docs/operations/p74-facebook-reference-ingestion.md` from the repository root.

```bash
refintel facebook-login
refintel facebook-page 'https://www.facebook.com/RawrNationTV' \
  --brand rawr-nation --rights owned --limit 12 --discover-only
refintel facebook-page 'https://www.facebook.com/RawrNationTV' \
  --brand rawr-nation --rights owned --limit 12 --local-vision
```

The browser profile and cookie jar stay local. Public share redirects are rejected; stable
page-ID or handle URLs are required.

## Frame extraction

Default processing uses adaptive evidence density and generates:

- a normalized analysis proxy;
- extracted WAV audio;
- technical metadata;
- frames every 2–5 seconds for most short-form references;
- frames at minute boundaries for long references;
- scene keyframes when PySceneDetect is available;
- a quality-filtered preferred frame gallery;
- a contact sheet and machine-readable manifests.

A custom interval can be selected:

```bash
refintel process <reference-id> --interval 30
```

Adaptive defaults:

| Reference duration | Interval |
| --- | ---: |
| up to 15 seconds | 2 seconds |
| 15–45 seconds | 3 seconds |
| 45–90 seconds | 5 seconds |
| 90–180 seconds | 10 seconds |
| 3–10 minutes | 30 seconds |
| over 10 minutes | 60 seconds |

Scene keyframes are added independently, so editorial cuts remain visible even
when they fall between interval frames.

For exhaustive motion analysis, pass `--every-frame`. This decodes every source frame and
writes change/brightness metrics without retaining thousands of redundant images:

```bash
refintel process <reference-id> --every-frame --local-vision
```

Each video run now also creates a typed temporal report. It combines measured every-frame
motion and cut candidates, WAV energy, transcript/caption timing, OCR from preferred frames,
and chronological local-model observations when available. Open it independently with:

```bash
refintel temporal-report <reference-id> --open-browser
```

The command is hash-resumable; use `--force` only when intentionally rebuilding unchanged
inputs. Missing optional modalities produce a `partial` report with named limitations instead
of invented evidence. In particular, actual motion is never asserted without every-frame
measurements, and still/slideshow-like sources are disclosed explicitly.

## Local browser application

```bash
refintel serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. This server is intended for local use. It is not deployed to Vercel.

## Deterministic fallback mode

The base pipeline works without a speech or visual model. It still produces:

- media metadata;
- frames and scene manifests;
- contact sheets;
- measured pacing data;
- rule-based hook/story sections;
- an offline HTML report;
- a reference fingerprint;
- an original brief starter.

Optional providers add richer transcription, visual descriptions, embeddings, and semantic search.

## Output structure

```text
workspace/
  library.sqlite3
  references/<reference-id>/
    project.json
    source/
    media/
      analysis.mp4
      audio.wav
      media_metadata.json
    frames/
      interval/
      scenes/
      preferred/
      frame_manifest.json
      contact_sheet.jpg
    transcript/
      transcript.txt
      transcript.json
      captions.srt
      captions.vtt
    analysis/
      reference_analysis.json
      every_frame_metrics.json
    reports/
      index.html
      temporal-report.json
      temporal.html
    exports/
      reference_fingerprint.json
      original_content_brief.json
    logs/
```

## Deployment-credit policy

P66 is intentionally isolated under `reference-engine/` and is excluded from the static Vercel bundle. GitHub CI uses offline fixtures. No Vercel preview is required for normal P66 development. A single optional UI integration deployment may be performed after the local engine is complete.
