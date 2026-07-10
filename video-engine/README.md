# P65 Actual Video Generation MVP

This package is the first real media-production layer in the content automation repository. It turns a structured Rawr Nation story project into a playable vertical MP4 using Remotion.

## Current output

- 1080×1920 vertical video
- 30 fps
- H.264 MP4
- 30–45 second template
- animated scene system
- phrase captions with semantic word highlighting
- Rawr Nation watermark and CTA
- disclosure and progress treatment
- optional ElevenLabs narration
- render manifest for review traceability

The sample is a production-system demonstration, not approved factual content. Its source record is intentionally marked `needs_verification`.

## Requirements

- Node.js 18 or newer
- npm
- Chrome/Chromium downloaded automatically by Remotion when required
- ElevenLabs credentials only when narration is needed

## Install

```bash
cd video-engine
npm install
```

## Validate the sample

```bash
npm run validate
```

Validation checks the schema, dimensions, duration, scene coverage, captions, source record, and mandatory human-review flag.

## Preview in Remotion Studio

```bash
npm run studio
```

Open the local URL and select `RawrNationShort`.

## Render immediately without an API key

```bash
npm run render
```

Output:

```text
video-engine/out/rawr-nation-army-ant-bridge-demo.mp4
video-engine/out/rawr-nation-army-ant-bridge-demo.render.json
```

This fallback render is caption-led and silent. It proves the composition, scene animation, captions, branding, and MP4 pipeline without using a paid service.

## Generate ElevenLabs narration

Never commit credentials. Set them in the shell or a local `.env` loader:

```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."
export ELEVENLABS_MODEL_ID="eleven_multilingual_v2"
npm run voice
```

The command uses ElevenLabs' speech-with-timestamps endpoint and writes:

```text
public/generated/rawr-nation-army-ant-bridge-demo.mp3
out/rawr-nation-army-ant-bridge-demo-alignment.json
out/rawr-nation-army-ant-bridge-demo-voiced.json
```

Render the voiced project:

```bash
node scripts/render.mjs out/rawr-nation-army-ant-bridge-demo-voiced.json
```

## Render another project

```bash
node scripts/validate-project.mjs path/to/project.json
node scripts/render.mjs path/to/project.json out/custom-name.mp4
```

The current composition supports the `vertical_short` format and these visual variants:

```text
hook
swarm
bridge
traffic
reveal
cta
```

## Project contract

A project contains:

- brand profile
- narration
- timed scenes
- timed caption chunks
- source records
- safety level for every scene
- engagement/compliance/monetization responsibility
- render settings
- disclosure
- CTA
- editorial status
- mandatory human-review flag

See `src/types.ts` and `samples/rawr-nation-army-ants.json`.

## What is real now

The current package genuinely renders an MP4. It does not merely produce a script or storyboard.

The visual layer is a reusable motion-graphics/illustrated reconstruction template. It does not yet generate cinematic AI footage, select licensed stock, render Blender scenes, upload assets, or publish to social platforms.

## Next production milestones

1. Connect verified research and script generation.
2. Convert ElevenLabs character alignment into regenerated phrase timing.
3. Add brand profiles for Animal X, Historiq, and Ani Films.
4. Add owned/licensed media ingestion.
5. Add a remote job queue, object storage, and container render worker.
6. Add browser job submission, preview, revision, and download.

## Guardrails

- No credentials in GitHub.
- No automatic publishing.
- No final approval automation.
- No unlicensed asset downloading.
- No claims are considered verified merely because they render successfully.
- Human editorial and policy review remains required.
