# P27 Platform Export Closeout Report

Part of #329. Closes #355 after the PR merges.

## Closeout purpose

This report closes P27 by confirming that platform export contracts, export pack helpers, example artifacts, and validation coverage are complete for the P27 short/social publishing workflow.

P27 remains a manual-review export layer. It does not upload content, connect platform accounts, approve rights, approve monetization, approve editorial status, or produce analytics feedback loops.

## Completed P27 scope

| Issue | Step | Status | Evidence |
| --- | --- | --- | --- |
| #350 | P27-01 — Define platform export directory contract | Complete | `docs/operations/p27-step-01.md`, `docs/operations/p27-export-directory-example.json`, `tests/integration/test_p27_step_01.py` |
| #351 | P27-02 — Generate YouTube Shorts export pack | Complete | `src/youtube_shorts_export.py`, `docs/operations/p27-step-02.md`, `docs/operations/p27-youtube-shorts-export-example.json`, `tests/integration/test_p27_step_02.py` |
| #352 | P27-03 — Generate TikTok, Instagram Reels, and Facebook Reels export packs | Complete | `src/short_form_exports.py`, `docs/operations/p27-step-03.md`, `docs/operations/p27-short-form-export-example.json`, `tests/integration/test_p27_step_03.py` |
| #353 | P27-04 — Generate X/Twitter caption and thread export pack | Complete | `src/x_twitter_export.py`, `docs/operations/p27-step-04.md`, `docs/operations/p27-x-twitter-export-example.json`, `tests/integration/test_p27_step_04.py` |
| #354 | P27-05 — Validate cross-platform export readiness | Complete | `src/export_readiness.py`, `docs/operations/p27-step-05.md`, `docs/operations/p27-cross-platform-readiness-example.json`, `tests/integration/test_p27_step_05.py` |
| #355 | P27-06 — P27 platform export closeout | In this PR | `docs/operations/p27-closeout-report.md`, `docs/operations/p27-closeout-checklist.json`, `tests/integration/test_p27_step_06.py` |

## Export packs confirmed

P27 confirms review-only export pack support for:

- YouTube Shorts via `exports/youtube_shorts/`;
- TikTok via `exports/tiktok/`;
- Instagram Reels via `exports/instagram_reels/`;
- Facebook Reels via `exports/facebook_reels/`;
- X/Twitter via `exports/x_twitter/`.

Each supported platform has documented or generated files, metadata, review status, and risk notes. All pack states remain:

```text
publish_allowed: false
review_required: true
is_publish_ready: false
```

## Validation coverage confirmed

P27 validation confirms:

- required platform folders are named consistently;
- required platform files are declared;
- metadata fields exist;
- review status fields exist;
- P26 risk state remains visible;
- blocking reasons and required actions carry through to review status;
- blocked content does not appear as `publish_ready`;
- P29 editorial approval remains required;
- manual review remains separate from publishing approval.

## Manual publishing workflow after P27

A human publishing operator may use the export pack outputs for review only. The workflow remains:

1. Review generated copy, metadata, and platform-specific notes.
2. Confirm P26 rights, monetization, source attribution, music, and originality status.
3. Complete P29 editorial approval before any publish-ready state.
4. Manually prepare platform uploads outside P27 only after approvals are recorded.

## Remaining direct-upload/API gaps

These gaps are intentionally out of scope for P27:

- YouTube API upload;
- TikTok API upload;
- Meta/Instagram/Facebook upload APIs;
- X API posting;
- platform credential storage;
- live platform post previews;
- platform analytics ingestion;
- engagement/reply scraping;
- automated music licensing;
- automatic rights clearance;
- automatic monetization approval;
- automatic editorial approval.

These can be considered in future epics only after explicit scoped issues, credential policies, approval governance, and safety requirements are defined.

## Parent epic closeout readiness

After this PR merges and #355 closes, parent epic #329 can be updated and closed if all child task checkboxes are complete.

## Stop conditions preserved

P27 must remain blocked if any future change attempts to:

- treat export readiness as publish approval;
- default `publish_allowed` to `true`;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- request or store platform credentials;
- add platform upload APIs without scoped governance;
- commit external rendered video assets;
- commit secrets;
- bypass workflow gates.

## Closeout decision

P27 is complete when:

- this report exists;
- the checklist exists;
- step-06 tests validate the P27 closeout artifacts;
- #350 through #355 are complete;
- exact-head CI passes before merge.

P27 is not a publishing approval system. It is a deterministic, review-only export and validation layer for manual publishing workflows.
