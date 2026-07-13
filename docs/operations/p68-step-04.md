# P68 Step 04

This step adds original concept generation and continuity-aware production planning for the High-Fidelity Original Content Pilot.

Part of #714. Closes #718 after the PR merges.

## Outcome

The planner creates three original concept options for either Rawr Nation or Animal X using only abstract reusable mechanics. A selected option becomes a structured original-content plan containing an original script, storyboard, 6–8 shots, continuity bible, visual identity, source-backed factual notes, clip prompts, audio bridges, and originality-distance evidence.

The target video is 25–38 seconds. Every shot must reserve at least 0.5 seconds of transition handle where generation permits.

## Continuity before clip generation

The continuity bible locks:

- subject identity, defining features, anatomy, wardrobe, proportions, and scale;
- environment and background geography, landmarks, weather, and time of day;
- lighting and time of day, including direction and quality;
- screen direction and subject movement;
- camera motion and framing language;
- color treatment and grade;
- continuous audio ambience unless a story beat motivates a change.

Each shot adds:

- story stage, duration, original narration, and readable caption;
- visual action and camera direction;
- entry and exit action for pose/action overlap;
- screen direction;
- direct, match, action, J-cut, or L-cut strategy;
- audio bridge, ambience, and motivated sound effect;
- transition handles;
- provider-neutral clip prompt and continuity-drift negative prompt.

Flashy transitions are not a continuity strategy. The prompts lock identity and environment and explicitly reject anatomy changes, background jumps, lighting flips, reversed movement, duplicate subjects, logos, watermarks, and embedded captions.

## Originality distance

Reference fingerprints may supply only abstract mechanics. The planner never treats source expression as reusable.

The automated check measures source wording similarity and blocks any verbatim source phrase of eight or more words. The threshold is a preliminary safety signal, not an originality approval. Human review must also compare premise, examples, visual composition, shot order, characters, branding, audio, and overall expression.

## Facts and approval gates

Every plan requires source-backed factual notes containing a claim and source URL. Those notes remain pending human factual review.

The planner does not generate clips, render video, call a media provider, download assets, or publish. It does not approve rendering, factual accuracy, rights, originality, advertiser suitability, monetization, or final creative quality.

Every output keeps `render_allowed: false`, `publish_allowed: false`, and `human_review_required: true`. P68-05 may accept a reviewed plan for clip production and natural stitching, but it must retain these gates.
