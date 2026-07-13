# P68 Step 05

This step implements provider-neutral short-clip production intake and natural FFmpeg assembly for the High-Fidelity Original Content Pilot.

Part of #714. Closes #719 after the PR merges.

## Outcome

The assembler accepts generated or approved clips, verifies exact planned shot order, provider lineage, rights status, prompt or asset references, and human assembly status, then creates a real reviewable MP4 and render manifest.

It does not call a clip-generation provider. This keeps generation replaceable: locally generated clips, future API-generated clips, owned footage, or licensed/approved clips use the same manifest contract.

## Clip normalization

Every accepted clip is probed and normalized with FFmpeg to:

- 1080×1920 vertical video;
- 30 fps;
- H.264/AAC video and stereo audio;
- 48 kHz audio;
- consistent pixel and sample formats;
- the planned shot duration after consuming part of its transition handles;
- fast-start MP4 output.

Clips that cannot cover the planned duration plus their transition handle fail before assembly. Silent clips receive a normalized silent audio stream so all clips remain technically compatible.

## Natural stitching

The visual transition schedule supports direct, action, and match cuts as first choices. J-cut and L-cut metadata allows narration or ambience to lead or trail a picture cut by a short controlled amount. Crossfades are limited to 300 ms and must be story motivated.

The implementation never adds flashy transitions to conceal identity, anatomy, environment, lighting, camera-motion, or screen-direction discontinuity. Those remain human continuity review blockers.

Normalized picture clips are concatenated without reordering. A finishing pass mixes continuous narration, music, and ambience across picture cuts, preserving audio continuity even when the shot source changes.

## Narration, sound, and captions

The finishing pass accepts:

- the local Kokoro narration already available in the repository, or another approved narration file;
- an approved music bed;
- zero or more approved SFX tracks;
- optional SRT/ASS captions for burn-in.

Clip audio is reduced beneath narration. Music and SFX use conservative starting levels. The final mix targets -14 LUFS with a -1.5 dB true-peak ceiling. These are technical defaults, not an audio-quality approval.

## Render manifest and failure safety

The render manifest records:

- shot order and normalized clip paths;
- source hashes, providers, and rights status;
- normalized and final media probes;
- transition and audio-bridge schedule;
- narration, music, SFX, and caption inputs;
- final output hash;
- technical pass status;
- blocking human reviews.

No automatic publishing or final approval is added. Every output retains `quality_approved: false`, `render_approved: false`, `publish_allowed: false`, and `human_review_required: true` until explicit factual, rights, originality, advertiser-suitability, continuity, narration, audio, caption, and final creative review occurs.
