# P24 Step 02

This step documents the platform mapping matrix for generated football content outputs.

Part of #326. Closes #333 after the PR merges.

## Goal

Map current and planned content outputs to YouTube Shorts, YouTube long-form, TikTok, Instagram Reels, Facebook Reels, and X/Twitter so operators can see which files are usable today, which files are review-only, which outputs can become publish candidates, and which assets remain missing for later P25 and P27 work.

## Source references

This mapping builds on:

```text
docs/operations/p24-step-01.md
README.md
src/cli.py
src/producer.py
src/explainer_producer.py
src/domain/render_status.py
src/assembler/preview_watermark.py
.github/workflows/p1-acceptance-harness.yml
```

## Mapping status

This platform mapping matrix is documentation-only.

It does not:

- generate platform exports;
- create upload descriptions;
- create title options;
- create thumbnails;
- create first-frame options;
- create hashtags;
- create pinned comments;
- render videos;
- upload to YouTube;
- upload to TikTok;
- upload to Instagram;
- upload to Facebook;
- post to X/Twitter;
- approve rights or monetization;
- bypass workflow gates.

## Platform readiness states

Use these states when assessing generated outputs:

| State | Meaning |
| --- | --- |
| `usable_now_review_only` | The file can help an operator review the content but must not be treated as publish-ready. |
| `usable_now_publish_candidate` | The file may become a publish candidate only after packaging, rights, and editorial review pass. |
| `planned_p25` | The asset belongs to YouTube packaging and retention work. |
| `planned_p26` | The asset belongs to monetization, rights, and originality safety work. |
| `planned_p27` | The asset belongs to platform-specific export pack work. |
| `planned_p28` | The asset belongs to long-form, series, and topic-intelligence work. |
| `planned_p29` | The asset belongs to human editorial review and publish-governance work. |
| `not_supported_today` | The repo does not currently generate the required output. |

## Current reusable output groups

| Output group | Current files | Current role |
| --- | --- | --- |
| Extraction evidence | `manifest.json`, clip pool `manifest.json` | Review topic, timestamps, source text, scores, and source asset lineage. |
| Short production plan | `production_plan.json` | Review short-form title, narration, segment order, clip references, and image search queries. |
| Explainer production plan | `explainer_plan.json` | Review explainer title, sections, narration, visual beats, clip references, and duration budgets. |
| Visual assets | `image_intro.png`, `image_*.png`, `beat_*.png`, `beat_comparison_collage.png` | Review visuals and potential cover/first-frame candidates. |
| Source evidence | `image_sources.json`, `checkpoint.json`, preview metadata | Review image sources, resume state, and preview publication status. |
| Audio assets | `narration_*.mp3`, background music when provided | Review voiceover and music usage risk. |
| Caption assets | `subtitles.srt` | Review caption timing for rendered outputs. |
| Rendered review assets | `preview_video.mp4`, `preview_video.mp4.metadata.json` | Review-only Short render; not publication eligible. |
| Rendered publish candidates | `publish_video.mp4`, explainer `final_video.mp4` | May become publish candidates only after later package, rights, export, and editorial gates. |

## Platform mapping matrix

| Platform | Usable current outputs | Missing assets | Review requirement | Current publish status |
| --- | --- | --- | --- | --- |
| YouTube Shorts | `preview_video.mp4`, `publish_video.mp4`, `production_plan.json`, `subtitles.srt`, `image_sources.json`, `manifest.json` | title options, first-frame options, upload description, hashtags, pinned comment, retention score, monetization risk report, rights review, export folder, editorial approval | Must review hook, first frame, title/description alignment, image sources, broadcast footage, music license, reused-content risk, and human approval | `preview_video.mp4` is review-only; `publish_video.mp4` is only a publish candidate after P25, P26, P27, and P29 controls. |
| YouTube long-form | `explainer_plan.json`, explainer `final_video.mp4`, `subtitles.srt`, `image_sources.json`, clip pool `manifest.json` | 16:9 render mode, long-form concept model, chapters, thumbnail concepts, source list, upload description, tags, retention structure, sponsor slot markers, rights review, editorial approval | Must review factual sourcing, chapter pacing, title/thumbnail promise, image/music/clip rights, and originality | Not supported as true long-form today; vertical explainer output is review-only or a future candidate, not a complete long-form package. |
| TikTok | vertical rendered video files, short narration, captions, visual assets | TikTok caption, TikTok hashtags, music-risk note, first-frame/cover guidance, platform export folder, rights/originality note | Must review music use separately, avoid assuming YouTube-safe audio is TikTok-safe, confirm caption style and no watermark mismatch | Manual repurpose only; no TikTok export pack or upload readiness today. |
| Instagram Reels | vertical rendered video files, visual assets, captions, `image_sources.json` | Reels caption, hashtags, cover-frame note, collaborator/tag note, music-risk note, rights/originality note, export folder | Must review cover frame, image rights, music rights, caption fit, brand safety, and originality | Manual repurpose only; no Reels export pack or upload readiness today. |
| Facebook Reels | vertical rendered video files, captions, source evidence | Facebook caption, hashtags, monetization/originality note, music-risk note, export folder, review status | Must review reused-content risk, music rights, image sources, clip rights, and platform monetization suitability | Manual repurpose only; no Facebook Reels export pack or upload readiness today. |
| X/Twitter | rendered video files, `production_plan.json`, `explainer_plan.json`, source evidence | short post copy, optional thread, hashtags, debate prompt, factual caveat, rights note, export folder | Must review factual accuracy, claims, debate framing, clip rights, and source context | Manual attachment/post only; no X/Twitter export pack or posting readiness today. |

## Platform-specific constraints

### YouTube Shorts

Required constraints:

- vertical 9:16 output;
- strong first frame;
- click-worthy title;
- short upload description;
- hashtags;
- pinned comment;
- no `preview_video.mp4` publication;
- rights and monetization review before upload;
- human approval before publish-ready state.

Current gap:

- The repo can generate vertical Short assets, but it does not yet generate a YouTube Shorts export pack.

### YouTube long-form

Required constraints:

- true 16:9 render support;
- 6-8 minute or configured long-form duration;
- chapter structure;
- thumbnail concepts;
- upload description;
- source list;
- retention structure;
- factual source review;
- rights and editorial approval.

Current gap:

- The repo creates vertical explainers, not a true YouTube long-form package.

### TikTok

Required constraints:

- vertical output;
- native short caption style;
- hashtags;
- first-frame/cover note;
- platform-safe music review;
- no assumption that background music is licensed for TikTok.

Current gap:

- The repo does not generate TikTok captions, hashtags, music-risk notes, or export folders.

### Instagram Reels

Required constraints:

- vertical output;
- cover-frame guidance;
- caption and hashtags;
- music rights note;
- original/reused-content review;
- no watermarked cross-platform repost output.

Current gap:

- The repo does not generate Instagram Reels-specific metadata or cover guidance.

### Facebook Reels

Required constraints:

- vertical output;
- caption and hashtags;
- monetization/originality note;
- music rights note;
- rights review for footage and images.

Current gap:

- The repo does not generate a Facebook Reels export pack or monetization note.

### X/Twitter

Required constraints:

- concise post copy;
- optional thread for explainers;
- debate prompt;
- factual caveat when stats/sources are unreviewed;
- rights note when video contains broadcast clips or web images.

Current gap:

- The repo does not generate post copy, thread copy, or debate prompts.

## Planned downstream asset ownership

| Missing asset | Target epic |
| --- | --- |
| title options | P25 |
| first-frame options | P25 |
| thumbnail concepts | P25 |
| retention score | P25 |
| hook score | P25 |
| CTA/comment-trigger options | P25 |
| monetization risk report | P26 |
| rights clearance status | P26 |
| originality assessment | P26 |
| source attribution checklist | P26 |
| music license note | P26/P27 |
| platform export folders | P27 |
| YouTube Shorts export pack | P27 |
| TikTok export pack | P27 |
| Instagram Reels export pack | P27 |
| Facebook Reels export pack | P27 |
| X/Twitter export pack | P27 |
| 16:9 long-form concept and output contract | P28 |
| series and calendar mapping | P28 |
| human editorial review status | P29 |
| publish-readiness manifest | P29 |

## Publish candidate rules

A generated output may be called a publish candidate only when:

- it is not a preview render;
- it has a content package reference;
- platform-specific metadata exists;
- rights and monetization risk are reviewed;
- source attribution requirements are reviewed;
- music license requirements are reviewed;
- originality requirements are reviewed;
- human editorial approval is recorded;
- the target platform export pack exists;
- no hard blocker remains open.

Until those controls exist, generated video files remain review assets or incomplete publish candidates.

## Stop conditions

Stop platform export or publishing work if:

- `preview_video.mp4` is selected for upload;
- a platform export is marked publish-ready without rights review;
- a platform export is marked publish-ready without human approval;
- a single caption is reused blindly across all platforms;
- background music is treated as safe for every platform;
- `image_sources.json` is treated as copyright clearance;
- broadcast clips are treated as rights-cleared by default;
- YouTube long-form is claimed supported without 16:9 output and long-form package fields;
- TikTok, Instagram, Facebook, or X/Twitter upload readiness is implied before P27;
- workflow gate bypass is requested.

## Guardrails

- No automatic platform export.
- No automatic upload.
- No automatic publishing.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic legal approval.
- No automatic music-license approval.
- No automatic thumbnail generation.
- No automatic title approval.
- No automatic editorial approval.
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
tests/integration/test_p24_step_02.py
```

The validation checks source references, documentation-only status, platform readiness states, output groups, platform mapping entries, platform-specific constraints, downstream asset ownership, publish candidate rules, stop conditions, guardrails, and P24 CI wildcard coverage.
