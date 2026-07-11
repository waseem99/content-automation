# Local Reference Intelligence Engine

This package ingests authorized social-video references or local files, decomposes them into measurable media artifacts, generates a synchronized local report, saves a reusable reference fingerprint, and exports an original production brief for the existing content workflow and P65 video renderer.

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
URL or local video
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

## Authorized URL ingestion

```bash
refintel ingest-url 'https://www.youtube.com/watch?v=...' \
  --rights permitted \
  --title "Authorized reference"
```

For an operator-owned session, cookies can be read locally by yt-dlp:

```bash
refintel ingest-url '<url>' \
  --rights owned \
  --cookies-from-browser chrome
```

The engine never uploads cookies or includes them in logs. If a platform extractor cannot access a video, use `ingest-file` as the supported fallback.

## Frame extraction

Default processing generates:

- a normalized analysis proxy;
- extracted WAV audio;
- technical metadata;
- frames at 00:00, 01:00, 02:00, and subsequent minute boundaries;
- scene keyframes when PySceneDetect is available;
- a quality-filtered preferred frame gallery;
- a contact sheet and machine-readable manifests.

A custom interval can be selected:

```bash
refintel process <reference-id> --interval 30
```

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
    reports/
      index.html
    exports/
      reference_fingerprint.json
      original_content_brief.json
    logs/
```

## Deployment-credit policy

P66 is intentionally isolated under `reference-engine/` and is excluded from the static Vercel bundle. GitHub CI uses offline fixtures. No Vercel preview is required for normal P66 development. A single optional UI integration deployment may be performed after the local engine is complete.
