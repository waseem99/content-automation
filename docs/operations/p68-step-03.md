# P68 Step 03

This step adds confidence-aware multimodal reference intelligence for the High-Fidelity Original Content Pilot.

Part of #714. Closes #717 after the PR merges.

## Goal

Turn authorized reference media into a useful creative-mechanics report without presenting inference as fact. The analysis combines local transcription, OCR/on-screen-text observations, local vision observations, measured edit timing, shot taxonomy, emotional beats, caption rhythm, audio cues, and story-stage estimates.

Human review remains mandatory. The output informs original concepts; it does not authorize copying or publication.

## Evidence provenance contract

Every `AnalysisFinding` records exactly one source class:

- `measured`: deterministic media metadata, frame timing, scene boundaries, or silence intervals;
- `model_observation`: local speech or vision model output tied to an evidence artifact;
- `deterministic_fallback`: an explicit heuristic or an unavailable-capability marker.

Every finding also records:

- confidence from 0 to 1;
- provider or fallback identifier;
- evidence artifact paths when evidence exists;
- `human_review_required: true`.

The report displays provenance, confidence, and provider next to each finding. It must never style deterministic fallback text as a measured fact or model observation.

## Multimodal outputs

The analysis now exposes:

- local transcript phrase timing and caption rhythm;
- model-observed on-screen text when reliable OCR-like output exists;
- model-observed shot taxonomy when local vision is enabled;
- frame-level emotional tone and motion clues from local vision;
- transcript-keyword emotional progression as a low-confidence fallback;
- measured scene timing without falsely treating cut timing as shot-size classification;
- measured silence/pause cues when available;
- speech density only as a weak audio-timing proxy when silence data is unavailable;
- duration-proportional story stages labeled as deterministic fallback;
- aggregate counts for measured, model-observed, and fallback findings;
- explicit reasons explaining why fallback behavior was used.

## Confidence-aware behavior

If local vision is disabled or fails, the engine records that shot size and on-screen text are unavailable. It does not invent OCR, shot labels, subjects, settings, emotional expressions, or motion.

If local transcription returns no segments, the engine records that caption rhythm is unavailable. It does not fabricate spoken wording.

If measured silence intervals are absent, the engine may expose speech density as a weak timing proxy, but it must not claim to recognize music, sound effects, ambience, or audio energy.

Model output stays an observation pending human verification. Provider failures are visible in the report and fallback-reason list.

## Local-first providers

P68-03 retains the existing local-first stack:

- faster-whisper for local transcription when installed;
- Ollama with a configured local vision model for frame observations;
- FFmpeg/ffprobe and PySceneDetect for measured media evidence;
- deterministic fallback behavior when optional local models are unavailable.

No paid API is required. No source media, frames, transcript, browser cookies, or model prompts are uploaded by this implementation.

## Originality and safety boundaries

The analysis may extract abstract mechanics such as hook speed, edit rhythm, caption density, story stages, emotional progression, and audio pause patterns.

It must not reuse or export source footage, exact wording, exact captions, shot-for-shot order, branding, watermarks, music, voices, characters, proprietary artwork, or unsupported factual claims into generated content.

No result is permission to publish. P68-04 must create a new concept and continuity plan, and later quality, factual, rights, originality, advertiser-suitability, and human-review gates still apply.

## Validation

Focused tests verify:

- all three provenance classes are represented and counted;
- OCR and shot taxonomy are model observations only when evidence exists;
- unavailable OCR and shot taxonomy are labeled as fallback rather than invented;
- caption rhythm and emotional progression retain their correct provenance;
- audio cues distinguish measured silence from weak proxy behavior;
- story stages identify their duration-proportional fallback basis;
- every finding and analysis package requires human review;
- the report exposes provenance and provider details.
