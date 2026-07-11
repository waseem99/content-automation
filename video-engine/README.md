# P65/P67 Local Video Generation Engine

This package turns structured, human-reviewable story projects into real 1080×1920 H.264 MP4 videos with Remotion. P67 adds a no-cost local narration path and brand-neutral compositions for original reference-inspired samples.

## Current output

- 1080×1920 vertical video
- 30 fps
- H.264/AAC MP4
- timed scenes and phrase captions
- semantic word highlighting
- brand watermark, disclosure, CTA, and progress treatment
- local Kokoro narration by default
- optional ElevenLabs narration
- render and timing manifests
- mandatory human review

The sample projects are demonstrations, not automatically approved publications.

## Requirements

- Node.js 18+
- npm
- Python 3.10+
- FFmpeg and ffprobe
- `espeak-ng` for Kokoro text normalization
- internet access once to download the open model weights

## Install

```bash
cd video-engine
npm install
python -m pip install -r voice-requirements.txt
```

On Ubuntu/Debian:

```bash
sudo apt-get install ffmpeg espeak-ng
```

## Available samples

```text
samples/rawr-nation-army-ants.json
samples/rawr-nation-blind-spot.json
samples/animal-x-elephant-ground-signals.json
```

The P67 samples use the `ReferenceStoryShort` composition and new visual themes:

```text
vision
elephants
```

## Validate

```bash
npm run validate:p67
npx tsc --noEmit
```

## Generate free local narration

Kokoro is the default provider. No API key is required:

```bash
node scripts/generate-voice.mjs samples/rawr-nation-blind-spot.json
node scripts/generate-voice.mjs samples/animal-x-elephant-ground-signals.json
```

Optional settings:

```bash
export VOICE_PROVIDER=kokoro
export KOKORO_VOICE=af_heart
export KOKORO_SPEED=1.08
```

The command writes:

```text
public/generated/<project-id>-kokoro.wav
out/<project-id>-kokoro-alignment.json
out/<project-id>-kokoro-voiced.json
```

Kokoro does not currently provide forced word alignment in this integration. The alignment file contains proportional word-timing estimates, while the full scene/caption timeline is scaled to the measured audio duration.

## Render the narrated samples

```bash
node scripts/render.mjs \
  out/rawr-nation-hidden-blind-spot-p67-kokoro-voiced.json \
  out/rawr-nation-hidden-blind-spot-p67.mp4

node scripts/render.mjs \
  out/animal-x-elephant-ground-signals-p67-kokoro-voiced.json \
  out/animal-x-elephant-ground-signals-p67.mp4
```

## Use ElevenLabs optionally

ElevenLabs remains available but is no longer the default:

```bash
export VOICE_PROVIDER=elevenlabs
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."
export ELEVENLABS_MODEL_ID="eleven_multilingual_v2"
node scripts/generate-voice.mjs path/to/project.json
```

Never commit credentials.

## Caption-only mode

```bash
VOICE_PROVIDER=caption_only node scripts/generate-voice.mjs path/to/project.json
```

Or render the original unvoiced project directly.

## Reference-driven production

P67 accepts P66 outputs:

```text
reference_fingerprint.json
original_content_brief.json
```

Use the project builder:

```bash
python ../reference-engine/scripts/p67_build_sample_project.py \
  --fingerprint /path/reference_fingerprint.json \
  --brief /path/original_content_brief.json \
  --template samples/rawr-nation-blind-spot.json \
  --output out/reference-tuned-project.json
```

The builder may carry forward only abstract mechanics:

- hook type and timing
- general story stages
- target visual-change rate
- target caption-change rate
- CTA placement
- engagement/safety/monetization priorities

It must not copy:

- exact wording
- source footage or shot composition
- source branding or watermarks
- source music or voice identity
- source characters or proprietary artwork
- a scene sequence shot-for-shot

## Project contract

A project contains:

- brand profile
- original narration
- timed scenes
- timed captions
- editorial sources
- safety and objective tags
- composition and visual theme
- render settings
- disclosure and CTA
- editorial status
- mandatory human-review flag

See `src/types.ts`.

## Guardrails

- No automatic publishing.
- No final approval automation.
- No source footage reuse by default.
- No claims are considered verified merely because they render.
- Rights, factual, originality, advertiser-suitability, and quality review remain human responsibilities.
