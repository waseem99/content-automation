# P24 Step 01

This step documents the current content output inventory and gap map for the football content automation pipeline.

Part of #326. Closes #332 after the PR merges.

## Goal

Record what the repository creates today, classify each output by operator use, identify documentation/code naming mismatches, and list the creator-ready publishing assets that are still missing before a run can be treated as a complete YouTube or multi-platform content package.

## Source references

This inventory builds on:

```text
README.md
src/cli.py
src/producer.py
src/explainer_producer.py
src/extractor/clip_pool.py
src/generator/script_generator.py
src/generator/explainer_script_generator.py
src/generator/image_generator.py
src/generator/visual_generator.py
src/assembler/mode_assembler.py
src/assembler/video_assembler.py
src/assembler/explainer_assembler.py
src/assembler/preview_watermark.py
src/domain/render_status.py
src/production_checkpoint.py
.github/workflows/p1-acceptance-harness.yml
```

## Inventory status

This current content output inventory is documentation-only.

It does not:

- extract match clips;
- generate scripts;
- fetch web images;
- generate AI images;
- generate voiceovers;
- assemble videos;
- render previews;
- render publish videos;
- upload to any platform;
- publish to YouTube;
- publish to TikTok;
- publish to Instagram;
- publish to Facebook;
- publish to X/Twitter;
- approve monetization readiness;
- clear rights or copyright risk;
- bypass workflow gates.

## Current pipeline commands

The repository currently exposes these content-production commands:

| Command | Current role | Primary output area |
| --- | --- | --- |
| `extract` | Analyze one full football video and extract ranked highlight clips | `data/output/{video_name}_{timestamp}/` |
| `manual-cut` | Smoke-test a manual timestamp clip | caller-selected output path |
| `extract-batch` | Build a shared clip pool from many videos for a concept campaign | `data/campaigns/{campaign}/clip_pool/` and `data/campaigns/{campaign}/extractions/` |
| `produce` | Generate a short-form production plan, web images, voiceover, subtitles, and assembled Short preview/publish artifact | `data/output/{run_folder}/production/` |
| `produce-explainer` | Generate a ~2 minute explainer plan, visuals, voiceover, checkpoint, subtitles, and final video | `data/campaigns/{campaign}/production/` |
| `list-voices` | List usable ElevenLabs voices for operator setup | terminal output only |

## Current extraction outputs

Single-video extraction creates:

| Output | Current path pattern | Classification | Operator use |
| --- | --- | --- | --- |
| `analysis_audio.wav` | `data/output/{run}/analysis_audio.wav` | Intermediate analysis asset | Used for transcription and energy analysis; not a publishing asset. |
| extracted clips | `data/output/{run}/clip_*.mp4` | Production source asset | Candidate real-footage moments for Shorts or explainers. |
| `manifest.json` | `data/output/{run}/manifest.json` | Operator evidence and production contract | Stores source video, topic, timestamps, scores, labels, and source text. |

The single-video `manifest.json` is the current bridge from extraction into short-form production.

## Current batch extraction outputs

Batch extraction creates:

| Output | Current path pattern | Classification | Operator use |
| --- | --- | --- | --- |
| copied concept | `data/campaigns/{campaign}/concept.yaml` | Production configuration snapshot | Records the concept used for the campaign. |
| per-video extraction folders | `data/campaigns/{campaign}/extractions/{video_stem}_{index}/` | Intermediate analysis assets | Holds per-source extraction artifacts. |
| shared clip files | `data/campaigns/{campaign}/clip_pool/*.mp4` | Production source assets | Entity-matched clips for explainer visual beats. |
| clip pool manifest | `data/campaigns/{campaign}/clip_pool/manifest.json` | Operator evidence and production contract | Stores concept id, title, source videos, entity labels, clip metadata, scores, and source text. |

The batch clip pool is currently required before `produce-explainer` can assemble a multi-entity explainer.

## Current Shorts production outputs

Short-form production creates or reuses:

| Output | Current path pattern | Classification | Operator use |
| --- | --- | --- | --- |
| `match_context.txt` | `data/output/{run}/production/match_context.txt` | Intermediate script context | Grounding material for OpenAI script generation. |
| `production_plan.json` | `data/output/{run}/production/production_plan.json` | Production plan | Contains title, topic, target duration, segment order, narration, web image queries, and clip references. |
| `image_intro.png` | `data/output/{run}/production/image_intro.png` | Visual asset | Intro still for Short. |
| `image_01.png`, `image_02.png`, `image_03.png` | `data/output/{run}/production/image_*.png` | Visual assets | Web-sourced stills for narrated setup, reaction, and closing segments. |
| `image_sources.json` | `data/output/{run}/production/image_sources.json` | Source evidence | Records image URLs, domains, titles, filter pass, dimensions, and segment labels. |
| `narration_*.mp3` | `data/output/{run}/production/narration_*.mp3` | Audio assets | ElevenLabs voiceover for narrated intro/image segments. |
| `subtitles.srt` | `data/output/{run}/production/subtitles.srt` | Caption timing asset | Word-group karaoke subtitle timing generated during assembly. |
| `preview_video.mp4` | `data/output/{run}/production/preview_video.mp4` | Review-only rendered asset | Default short-form render because `run_production` defaults to `RenderMode.PREVIEW`. |
| `preview_video.mp4.metadata.json` | `data/output/{run}/production/preview_video.mp4.metadata.json` | Review evidence | Marks preview output as `NOT_FOR_PUBLICATION` and `publication_eligible: false`. |
| `publish_video.mp4` | `data/output/{run}/production/publish_video.mp4` | Publish candidate only after approval | Produced only when publish render mode is used by the caller. |

## Current explainer production outputs

Explainer production creates or reuses:

| Output | Current path pattern | Classification | Operator use |
| --- | --- | --- | --- |
| `explainer_plan.json` | `data/campaigns/{campaign}/production/explainer_plan.json` | Production plan | Contains concept id, title, sections, narration, beat durations, visual beat types, image prompts, search queries, clip references, and caption highlights. |
| `beat_{section}_{index}.png` | `data/campaigns/{campaign}/production/beat_*.png` | Visual asset | Per-beat web or AI visual for explainer sections. |
| `beat_comparison_collage.png` | `data/campaigns/{campaign}/production/beat_comparison_collage.png` | Composite visual asset | Generated collage for comparison sections when enough panels exist. |
| `image_sources.json` | `data/campaigns/{campaign}/production/image_sources.json` | Source evidence | Records web image sources and AI/fallback visual entries. |
| `narration_{section}.mp3` | `data/campaigns/{campaign}/production/narration_*.mp3` | Audio asset | Section-level ElevenLabs voiceover. |
| `checkpoint.json` | `data/campaigns/{campaign}/production/checkpoint.json` | Resume state | Tracks script, image, voice, and assembly completion for reruns. |
| `subtitles.srt` | `data/campaigns/{campaign}/production/subtitles.srt` | Caption timing asset | Keyword caption timing generated during assembly. |
| `final_video.mp4` | `data/campaigns/{campaign}/production/final_video.mp4` | Rendered explainer asset | Current final assembled explainer output. |

## Current output classifications

Current outputs fall into these categories:

- **Production source assets:** extracted clips, clip pool clips, source concept copy.
- **Intermediate analysis assets:** `analysis_audio.wav`, per-video extraction folders, `match_context.txt`.
- **Production plans:** `production_plan.json`, `explainer_plan.json`.
- **Visual assets:** intro images, numbered images, beat images, comparison collage.
- **Audio assets:** narration MP3 files, background music when supplied externally.
- **Caption assets:** `subtitles.srt`.
- **Source evidence:** `manifest.json`, clip pool `manifest.json`, `image_sources.json`, `checkpoint.json`.
- **Rendered review assets:** `preview_video.mp4`, preview metadata.
- **Rendered publish candidates:** `publish_video.mp4` for Shorts when explicitly produced, `final_video.mp4` for explainers subject to future approval rules.

## README and code mismatch

The README currently documents short-form production output as `final_video.mp4` under `data/output/{run_folder}/production/`.

The code path in `src/producer.py` currently defaults `run_production` to `RenderMode.PREVIEW`, which writes `preview_video.mp4` by default and only writes `publish_video.mp4` when publish mode is used by the caller.

The preview path also writes preview metadata stating the render is not for publication.

This mismatch must be resolved in later P24/P29 work by documenting preview versus publish render behavior clearly and exposing or controlling render mode through an approved package workflow.

## Current publish-readiness gap

The current repository can create video files, but it does not yet create a complete creator-ready or monetization-ready package.

Missing creator-ready assets include:

- `content_package.json`;
- title options;
- first-frame options;
- thumbnail concepts;
- upload description;
- hashtags;
- pinned comment;
- platform-specific caption variants;
- retention score;
- hook score;
- CTA/comment-trigger options;
- rights clearance status;
- monetization risk report;
- originality assessment;
- source attribution checklist;
- music license note;
- platform export folders;
- human editorial review status;
- publish-readiness manifest.

## Platform suitability today

| Platform | Current suitability | Gap |
| --- | --- | --- |
| YouTube Shorts | Vertical MP4 can be created, but package is incomplete | Needs title, description, hashtags, pinned comment, first-frame guidance, retention score, rights risk, and approval status. |
| YouTube long-form | Not currently implemented as 16:9 long-form output | Needs long-form concept model, 16:9 assembly plan, chapters, thumbnail package, and source list. |
| TikTok | Vertical MP4 may be repurposed manually | Needs TikTok caption style, hashtags, music-risk note, and platform-safe export pack. |
| Instagram Reels | Vertical MP4 may be repurposed manually | Needs Reels caption, cover-frame guidance, hashtags, and rights note. |
| Facebook Reels | Vertical MP4 may be repurposed manually | Needs Facebook caption, rights/originality note, and monetization-risk note. |
| X/Twitter | Video may be manually attached | Needs post copy, thread summary, debate prompt, hashtags, and factual/risk caveat. |

## Required next-step package fields

P24 should move toward a `content_package.json` contract with at least these sections:

- run identity;
- content type;
- source assets;
- generated assets;
- production plans;
- rendered assets;
- platform suitability;
- missing assets;
- packaging placeholders;
- retention placeholders;
- rights and monetization placeholders;
- export placeholders;
- editorial review placeholders;
- next actions.

## Stop conditions

Stop P24 output packaging work if:

- generated outputs are described as publish-ready without review;
- `preview_video.mp4` is treated as publication eligible;
- `final_video.mp4` naming is used without clarifying whether the asset is a review render or publish candidate;
- `image_sources.json` is treated as copyright clearance;
- a web image filter is treated as legal approval;
- extracted broadcast footage is treated as rights-cleared;
- a background music file is treated as licensed for every platform;
- platform upload is implied;
- monetization approval is implied;
- human editorial review is skipped;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic rendering.
- No automatic publishing.
- No automatic upload.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic legal approval.
- No automatic platform export.
- No automatic external distribution.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.

## Validation

Covered by:

```text
tests/integration/test_p24_step_01.py
```

The validation checks source references, documentation-only status, command inventory, extraction outputs, Shorts outputs, explainer outputs, classification categories, README/code mismatch, missing creator-ready assets, platform suitability gaps, stop conditions, guardrails, and P24 CI wildcard coverage.
