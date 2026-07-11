# P68 Step 01

This step defines the quality benchmark and approved-reference-pack contract for the High-Fidelity Original Content Pilot.

Part of #714. Closes #715 after the PR merges.

## Goal

Define what “high quality” means before P68 downloads more references, generates new visual assets, creates clips, stitches clips, or renders the six-video pilot batch.

The machine-readable contract is:

```text
docs/operations/p68-quality-benchmark.json
```

## Starting point

P65–P67 proved that the repository can:

- render 1080×1920 H.264/AAC videos;
- generate local Kokoro narration;
- download and analyze an authorized direct Facebook reel;
- extract interval and scene frames;
- build reference fingerprints and original-content briefs;
- convert reusable mechanics into an original Remotion project;
- keep downloaded source media out of generated artifacts.

The P67 samples are technical proofs. They are not the P68 creative benchmark because their visuals remain simple, template-led motion graphics and their narration, factuality, originality, music, sound design, and creative quality still require human review.

## Contract status

This step is documentation and contract focused.

It does not:

- download reference media;
- generate images or clips;
- stitch clips;
- render new videos;
- deploy a media worker;
- upload or publish content;
- approve facts, rights, originality, advertiser suitability, monetization, or final creative quality;
- bypass any workflow or human-review gate.

## Pilot scope

P68 will produce six reviewable pilot videos:

- three for `rawr_nation`;
- three for `animal_x`.

Historiq and Ani Films remain the next brand-adaptation step after the first two production formats meet the P68 benchmark.

Every pilot must be:

- 1080×1920;
- 30 fps;
- H.264/AAC;
- 25–38 seconds;
- 6–8 shots;
- understandable without sound;
- complete with narration, captions, music, sound effects, and a narrative payoff;
- explicitly pending human approval until the final review is recorded.

## Quality decision

A video becomes a `production_candidate` only when:

- its weighted benchmark score is at least 8.0/10;
- no dimension scores below 7/10;
- every hard gate scores at least 8/10;
- factual, rights, originality, and advertiser-suitability evidence is present;
- a human reviewer records the decision;
- `publish_allowed` remains false until a separate publication decision.

A technically valid MP4 is not automatically a production candidate.

## Scoring dimensions

The benchmark weights total 100:

| Dimension | Weight | Minimum | Gate |
| --- | ---: | ---: | --- |
| First-second thumb stop | 10 | 8 | Quality |
| Story clarity and payoff | 10 | 8 | Quality |
| Shot and visual quality | 15 | 8 | Quality |
| Natural continuity and stitching | 15 | 8 | Quality |
| Narration performance | 8 | 7 | Quality |
| Music, SFX, and audio finish | 7 | 7 | Quality |
| Caption readability and timing | 5 | 8 | Quality |
| Factual accuracy and evidence | 8 | 8 | Hard gate |
| Rights and source handling | 7 | 8 | Hard gate |
| Originality distance | 8 | 8 | Hard gate |
| Advertiser suitability | 4 | 8 | Hard gate |
| Monetization readiness | 3 | 7 | Quality |

## Reference-pack contract

Each brand must have at least three authorized direct-video references before the P68 pilot batch is planned.

Each entry must record:

- `reference_id`;
- `brand_profile`;
- `platform`;
- `direct_video_url_or_local_file`;
- `rights_declaration`;
- `analysis_purpose`;
- `allowed_mechanics`;
- `excluded_source_specific_elements`;
- `human_review_status`.

References may influence only abstract mechanics such as:

- hook speed and type;
- story stages;
- average shot duration;
- caption density;
- visual-change rate;
- emotional progression;
- CTA placement;
- audio-energy pattern;
- platform-specific safe-zone behavior.

References must not supply:

- exact scripts or captions;
- source footage or source frames in the final render;
- source shot composition or shot-for-shot ordering;
- source branding, watermarks, music, voices, characters, or proprietary artwork;
- unverified factual claims.

## Generated clips and natural stitching

P68 may generate short clips and stitch them into one finished story. Clip generation is acceptable only when the continuity plan is created before generation.

Every planned clip must describe:

- subject identity and defining features;
- environment and background;
- time of day and lighting direction;
- color palette and grade;
- camera position, lens feeling, and camera movement;
- subject movement and screen direction;
- entry pose/action and exit pose/action;
- at least 0.5 seconds of usable transition handle where generation permits;
- intended narration, ambience, music, and sound-effect bridge;
- preferred cut strategy.

The stitcher must check:

- subject identity consistency;
- environment and background consistency;
- lighting and time-of-day consistency;
- wardrobe or anatomy consistency;
- screen-direction consistency;
- camera-motion compatibility;
- action overlap or pose bridge;
- first/last-frame compatibility;
- color palette and grade consistency;
- audio ambience continuity;
- narration/music/SFX bridging;
- whether the transition is motivated by the story.

Preferred transitions are direct cuts, match cuts, action cuts, J-cuts, L-cuts, and brief crossfades under 300 ms. Flashy transitions must not be used to hide unrelated or inconsistent clips.

## Rawr Nation benchmark

Rawr Nation should feel like a premium factual explainer:

- immediate mystery or contradiction;
- a clear visual demonstration rather than a text-only lecture;
- fast, credible explanation;
- distinct reveal or payoff;
- accessible language without unverified sensationalism;
- no generic slideshow or flat template-only diagram sequence.

## Animal X benchmark

Animal X should feel like a respectful wildlife micro-documentary:

- recognizable animal subject;
- believable environment and anatomy;
- behavior-led visual sequence;
- wonder without anthropomorphic misinformation;
- evidence-backed reveal;
- no cartoon-only placeholder visuals, graphic distress, or invented science.

## Review record requirements

The later pilot review record must include:

- reviewer identity or role;
- benchmark version;
- all dimension scores and evidence notes;
- weighted score;
- hard-gate results;
- blocking issues;
- required revisions;
- factual sources;
- rights and originality evidence;
- technical media probe;
- decision: `reject`, `major_revision`, `minor_revision`, or `production_candidate`;
- `publish_allowed: false` unless a separate publication decision exists.

## Downstream sequence

After this step:

1. P68-02 validates direct-video ingestion and adaptive frame sampling.
2. P68-03 adds richer transcript, OCR, vision, story, and audio analysis.
3. P68-04 generates original concepts and continuity-aware shot plans.
4. P68-05 generates or accepts short clips and stitches them naturally.
5. P68-06 renders the six-video batch and closes P68 with real review evidence.

