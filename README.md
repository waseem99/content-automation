# YouTube Automation — Clip Extraction (Phase 1)

Extract highlight clips from full football match videos using scene detection, audio energy spikes, and speech transcription matched to your topic.

## Prerequisites

1. **Python 3.11+**
2. **ffmpeg** on PATH — verify with `ffmpeg -version`

### Install ffmpeg (Windows)

Download from [gyan.dev ffmpeg builds](https://www.gyan.dev/ffmpeg/builds/) or:

```powershell
winget install Gyan.FFmpeg
```

## Setup

```powershell
cd c:\Users\PC\Documents\youtube_automation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you want to override Whisper model/device defaults.

## Usage

1. Place your full match video in `data/input/`
2. Run extraction:

```powershell
python -m src.cli extract `
  --video data/input/match.mp4 `
  --topic "Neymar injury 2014 and comeback FIFA 2026" `
  --count 4 `
  --duration 7
```

3. Clips and `manifest.json` are written to `data/output/{video_name}_{timestamp}/`

### Useful flags

| Flag | Default | Description |
|------|---------|-------------|
| `--count` | 4 | Number of clips |
| `--duration` | 7 | Clip length (seconds) |
| `--min-gap` | 15 | Minimum gap between clips |
| `--max-duration` | none | Analyze only first N seconds (faster testing) |
| `--whisper-model` | small | faster-whisper model size |
| `--whisper-device` | cpu | `cpu` or `cuda` |

### Manual clip test (smoke test)

```powershell
python -m src.cli manual-cut `
  --video data/input/match.mp4 `
  --start 2:55 `
  --end 3:02 `
  --output data/output/test_clip.mp4
```

## Output manifest

Each run produces `manifest.json` with timestamps, scores, and labels — this becomes the contract for later pipeline phases (AI script, images, ElevenLabs voiceover).

## Phase 2 — Script, Web Images, Voiceover, Assembly

After clip extraction, produce a 35–40s Short with an intro hook, 3 web-sourced images, and 1–2 real clips.

### 1. Add API keys

Copy `.env.example` to `.env` and fill in:

```env
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...    # from elevenlabs.io → Voices
```

Get a SerpAPI key at [serpapi.com](https://serpapi.com/) (Google Images search).

### 2. Run production

```powershell
python -m src.cli produce `
  --run-dir "data/output/your_run_folder" `
  --topic "Neymar injury in 2014 vs Colombia" `
  --clips "clip_04_crowd_reaction.mp4,clip_07_injury.mp4" `
  --target-duration 38 `
  --clip-duration 9 `
  --bg-music "data/assets/background.mp3" `
  --bg-music-volume 0.12 `
  --regenerate-script
```

Place your music file in `data/assets/` (any length — it is trimmed to match the final video).

To re-assemble only (reuse script/images/voice, add or change music):

```powershell
python -m src.cli produce `
  --run-dir "data/output/your_run_folder" `
  --topic "your topic" `
  --clips "clip_04_crowd_reaction.mp4,clip_07_injury.mp4" `
  --skip-images `
  --skip-voice `
  --bg-music "data/assets/background.mp3" `
  --bg-music-volume 0.12
```

### Output

```
data/output/{run_folder}/production/
├── production_plan.json   # script + image search queries
├── image_intro.png
├── image_01.png
├── image_02.png
├── image_03.png
├── image_sources.json     # URLs + domains for each downloaded image
├── narration_01.mp3       # intro
├── narration_02.mp3
├── narration_04.mp3
├── subtitles.srt          # word-group karaoke timings
└── final_video.mp4
```

### Video structure

| Segment | Content |
|---------|---------|
| 1 | Intro hook — web image + voiceover + karaoke captions |
| 2 | Web image + voiceover (setup) |
| 3 | Real clip (~9s, no captions) |
| 4 | Web image + voiceover (reaction) |
| 5 | Real clip or web image + voiceover (closing) |

Visual polish: Ken Burns zoom on stills, crossfade transitions between segments.

### Image sources (web search)

Images are fetched via **SerpAPI** (Google Images), not OpenAI image generation.

**Copyright filters applied automatically:**
1. Wikimedia Commons search first (`site:commons.wikimedia.org`)
2. Fallback: Creative Commons license filter (`sur:cl`)
3. Domain blocklist (Getty, Shutterstock, Reuters, AP, etc.)
4. Keyword blocklist (`getty`, `reuters`, `watermark`, etc.)
5. Preferred domains: Wikimedia, Pexels, Pixabay

**Important:** Filters reduce risk but do **not** guarantee copyright clearance. Review `image_sources.json` before uploading to YouTube. CC images may require attribution.

**Manual override:** Place your own PNGs as `image_intro.png`, `image_01.png`, etc. in `production/` and run with `--skip-images`.

### Production flags

| Flag | Purpose |
|------|---------|
| `--target-duration` | Total video length target (default 38s) |
| `--clip-duration` | Seconds per clip segment (default 9s) |
| `--regenerate-script` | Force new script (adds intro segment) |
| `--skip-images` | Reuse existing images |
| `--skip-voice` | Reuse existing voiceovers |
| `--skip-assembly` | Only generate script/images/audio |
| `--bg-music` | Background music path (trimmed to video length) |
| `--bg-music-volume` | Music volume 0.0–1.0 (default 0.12 = quiet) |
| `--no-captions` | Disable burned-in karaoke captions |

## Phase 3 — Explainer Videos (~2 minutes)

Config-driven explainers for multi-entity topics (e.g. four hyped players, countries, how FIFA works). Uses **many input videos** → shared **clip pool** → one **~2 min final video** with dynamic visual beats.

### Concept files

Define structure in [`concepts/`](concepts/) YAML files. Example: [`concepts/four_hyped_players_wc2026.yaml`](concepts/four_hyped_players_wc2026.yaml).

Each concept specifies:
- Extraction topics (one per input video)
- Section structure (hook, entity blocks, comparison, CTA)
- Stats/context for script generation
- Per-section duration budgets

### 1. Build clip pool (8–9+ input videos)

**Important:** each input video filename must include the player name (e.g. `Messi`, `Haaland`, `Mbappe`, `Yamal`). Clips are matched by **filename**, not folder order.

```bash
python -m src.cli extract-batch \
  --concept concepts/four_hyped_players_wc2026.yaml \
  --videos "data/input/*.mp4" \
  --campaign-dir data/campaigns/wc2026_players
```

Output:
```
data/campaigns/wc2026_players/
├── concept.yaml
├── clip_pool/
│   ├── manifest.json
│   └── *.mp4
└── extractions/
```

### 2. Produce explainer

```bash
python -m src.cli produce-explainer \
  --campaign-dir data/campaigns/wc2026_players \
  --concept concepts/four_hyped_players_wc2026.yaml \
  --voice-id YOUR_VOICE_ID \
  --bg-music data/assets/background.mp3 \
  --regenerate-script
```

### Explainer output

```
data/campaigns/{campaign}/production/
├── explainer_plan.json      # sections + visual beats
├── beat_hook_00.png         # per-beat images (web + AI)
├── narration_hook.mp3       # per-section voiceover
├── narration_messi.mp3
├── image_sources.json
├── checkpoint.json          # resume state (script/images/voice/assembly)
├── subtitles.srt            # keyword highlights
└── final_video.mp4
```

### Visual pipeline

| Beat type | Source |
|-----------|--------|
| `web_image` | SerpAPI (player photos, CC-filtered) |
| `web_image` + `cinematic_edit` | SerpAPI photo → GPT image **edit** for documentary polish (comparison/CTA) |
| `ai_image` | OpenAI generate (generic archetypes only — no player names) |
| `clip` | Match clips from clip pool |

**Public-figure safety:** OpenAI blocks prompts that name real players. Comparison/CTA use **SerpAPI + cinematic edit** instead. Player names are OK in SerpAPI search queries; AI prompts use archetypes only (`Argentina legend`, not `Messi`).

Beats are short (0.7–4s) with quick cuts — not one static image for 10+ seconds.

**GPT image settings** (good quality, controlled cost — upscaled to 1080×1920 in assembly):

```env
OPENAI_IMAGE_MODEL=gpt-image-1.5
OPENAI_IMAGE_SIZE=1024x1536
OPENAI_IMAGE_QUALITY=medium
```

Cheaper demo preset: `1024x1024` + `low`. Avoid `high` unless you need final publish quality.

### Explainer flags

| Flag | Purpose |
|------|---------|
| *(default)* | **Resume** from `production/checkpoint.json` — reuses plan, images, voice, video |
| `--regenerate-script` | Force new OpenAI script (costs tokens) |
| `--regenerate-images` | Regenerate all beat images |
| `--regenerate-voice` | Regenerate all section voiceovers |
| `--regenerate-assembly` | Re-render final video |
| `--skip-images` | Never call image APIs; use files on disk only |
| `--skip-voice` | Never call ElevenLabs; use MP3s on disk only |
| `--skip-assembly` | Only generate script/images/audio |
| `--voice-id` | Optional; must be from `list-voices` (premade on your account) |
| `--no-captions` | Disable keyword caption overlays |

**Token-saving workflow:** run once without regenerate flags. If voice fails, fix `.env` and re-run — script and images are reused automatically.

```bash
python -m src.cli list-voices   # pick a premade voice_id for .env
```

Checkpoint file: `data/campaigns/{campaign}/production/checkpoint.json`

### New concepts

Copy an existing YAML in `concepts/` and edit `sections`, `extraction.topics`, and `stats`. Works for players, countries, FIFA rules, or any multi-entity explainer.

## Notes

- Long videos take time on CPU (scene detection + Whisper). Use `--max-duration 300` for quick tests.
- Moment detection is heuristic; review `manifest.json` and re-run with adjusted topic if needed.
- Real broadcast footage may have copyright restrictions.
