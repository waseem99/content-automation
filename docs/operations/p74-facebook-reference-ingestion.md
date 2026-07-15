# P74 Facebook reference ingestion and storytelling analysis

P74 extends the local Reference Intelligence Engine with an authenticated, rights-gated
Facebook page workflow. It does not bypass login, CAPTCHA, private-page controls, DRM, or
platform access restrictions. Use it only for pages and videos the operator is authorized
to access and analyze.

## What the workflow measures

For each discovered video it produces:

- the locally downloaded source and a normalized analysis proxy;
- an exact decoded-frame timeline with change and brightness measurements for every frame;
- scene boundaries, chronological keyframes, preferred frames, and a contact sheet;
- local speech transcription with timestamps and caption files;
- isolated-frame observations for shot type, visible text, emotion, and motion;
- sequence-level analysis of the hook, story arc, visual progression, editing mechanics,
  emotional progression, payoff, reusable mechanics, and elements that must not be copied;
- an offline HTML report, reference fingerprint, and originality-safe brief starter.

Every decoded frame is measured, but thousands of near-identical JPEGs are not retained.
Scene keyframes and interval frames provide reviewable visual evidence while
`frames/every_frame_metrics.json` preserves the full frame-by-frame measurement timeline.

## Install locally

```bash
cd reference-engine
python -m venv .venv
source .venv/bin/activate
pip install -e '.[all,dev]'
playwright install chromium
```

Install and start Ollama with the configured vision model for sequence understanding. The
pipeline falls back to measured pacing, scenes, and transcript analysis when Ollama is not
available, and records that limitation explicitly.

## Create the authorized browser session once

```bash
refintel facebook-login
```

Chromium opens using a dedicated profile outside the repository. Log into the authorized
Facebook account and return to the terminal. Never share or commit that profile or its
cookie file.

## Discover only

```bash
refintel facebook-page 'https://www.facebook.com/RawrNationTV' \
  --brand rawr-nation \
  --rights owned \
  --limit 12 \
  --discover-only
```

Use this first to confirm page access and discovered URLs without downloading media.

## Download and analyze

```bash
refintel facebook-page 'https://www.facebook.com/RawrNationTV' \
  --brand rawr-nation \
  --rights owned \
  --limit 12 \
  --local-vision
```

Repeat for the other stable page URLs. The batch continues after an individual video
failure and records sanitized diagnostics. It does not publish, generate paid media, or
deploy anything to Vercel.

To run the same controlled workflow for all four configured brands:

```bash
python ../scripts/p74_run_facebook_portfolio.py \
  --rights owned \
  --limit 6 \
  --discover-only

python ../scripts/p74_run_facebook_portfolio.py \
  --rights owned \
  --limit 6
```

The first command is the recommended access check. The second downloads and analyzes up
to six discovered videos per configured active brand. Use repeated `--brand` options to
limit a run, for example `--brand historiq --brand ani-films`.

## Interpretation boundary

This engine learns transferable mechanics such as pacing, hook timing, escalation, visual
change density, caption rhythm, and reveal structure. It must not reproduce exact scripts,
shots, artwork, characters, branding, music, voices, or watermarks from source videos.
