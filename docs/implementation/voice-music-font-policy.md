# Approved Voice, Music, and Font Policy

## Publish rule

Publish outputs must not rely on raw provider configuration alone. A value in `.env`, such as `ELEVENLABS_VOICE_ID`, is only a provider identifier. It is not approval.

Before publish narration, the workflow must reference an approved internal `approved_voices.id` record. The policy service verifies:

- provider and provider voice ID match the approval record;
- approval status is `approved`;
- the voice is not preview-only;
- the approval has not expired or been revoked;
- the requested language and platform are allowed;
- the requested use is not prohibited;
- cloned voices have canonical consent evidence.

## Preview rule

Preview mode may use an unknown provider voice only when explicitly marked as a development voice. Preview output remains non-publication material and cannot enter a publication package.

## Cloned voices

A cloned voice can only be approved when `consent_evidence_asset_id` points to a canonical `license_evidence` asset whose metadata contains `evidence_type = consent`.

## Music and fonts

Background music and fonts are normal assets. Before they enter a publish manifest or publish render, they must pass the rights gate for the requested platform, territory, campaign and use. Music must be an `audio` asset. Fonts must be a `font` asset.

## Narration audit

Every generated narration intended for publish must be recorded in `football_brief.narration_outputs` with:

- workflow and optional manifest/stage references;
- mode, platform and language;
- SHA-256 hash of the input text;
- approved voice ID;
- provider, provider voice ID, provider request ID and model ID;
- output asset ID and output SHA-256.

## Backfill guidance

Existing configured voice and music values should be backfilled as follows:

1. Register the existing provider voice in `approved_voices` as `pending`.
2. Attach consent evidence before approving any cloned voice.
3. Mark development/test voices as `preview_only = true`.
4. Register existing background music as `audio` assets.
5. Attach license evidence and approve platform-specific rights before publish.
6. Register font files as `font` assets and approve platform-specific rights before publish.
7. Do not migrate `.env` voice IDs directly to approved status without human review.
