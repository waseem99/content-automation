# P25 YouTube Packaging and Retention Closeout Checklist

Parent epic: #327
Final closeout issue: #343
Final closeout PR: PR_NUMBER_PENDING

## Closeout scope

This checklist closes P25 YouTube packaging and retention readiness.

It confirms that P25 added a hook/retention rubric, title option helper, first-frame/thumbnail concept helper, retention score report helper, CTA/comment-trigger helper, readiness report, and final validation coverage.

## Required files

- [x] `docs/operations/p25-step-01.md`
- [x] `docs/operations/p25-step-02.md`
- [x] `docs/operations/p25-step-03.md`
- [x] `docs/operations/p25-step-04.md`
- [x] `docs/operations/p25-step-05.md`
- [x] `docs/operations/p25-title-options-example.json`
- [x] `docs/operations/p25-visual-concepts-example.json`
- [x] `docs/operations/p25-retention-score-example.json`
- [x] `docs/operations/p25-cta-library-example.json`
- [x] `docs/operations/p25-readiness-report.md`
- [x] `docs/operations/p25-closeout-checklist.md`
- [x] `src/title_options.py`
- [x] `src/visual_concepts.py`
- [x] `src/retention_score.py`
- [x] `src/cta_library.py`
- [x] `tests/integration/test_p25_step_01.py`
- [x] `tests/integration/test_p25_step_02.py`
- [x] `tests/integration/test_p25_step_03.py`
- [x] `tests/integration/test_p25_step_04.py`
- [x] `tests/integration/test_p25_step_05.py`
- [x] `tests/integration/test_p25_step_06.py`

## Child issue closure evidence

- [x] #338 closed through PR #381.
- [x] #339 closed through PR #382.
- [x] #340 closed through PR #383.
- [x] #341 closed through PR #384.
- [x] #342 closed through PR #385.

## Final PR placeholder status

- [x] Final closeout files initially use `PR_NUMBER_PENDING`.
- [ ] Final closeout files are patched with the actual PR number before merge: PR_NUMBER_PENDING.
- [ ] Final closeout PR passes exact-head CI.
- [ ] Final closeout PR is merged only after required checks pass.
- [ ] #343 is confirmed closed after merge.
- [ ] Parent epic #327 is updated with final PR, merge commit, and exact-head CI evidence.
- [ ] Parent epic #327 is closed as completed.

## Required exact-head checks

The final closeout PR must pass these checks on the exact current PR head SHA:

- `P1 Acceptance Harness`
- `P1 Foundation Closeout`
- `P1 Ops Storage`

## P25 readiness checklist

- [x] Hook and retention scoring rubric documented.
- [x] First 1 second thumb-stop criteria documented.
- [x] First 3 seconds clarity criteria documented.
- [x] First 8 seconds retention-lock criteria documented.
- [x] Midpoint reset criteria documented.
- [x] CTA/comment-trigger criteria documented.
- [x] Title option helper implemented.
- [x] First-frame and thumbnail concept helper implemented.
- [x] Retention score report helper implemented.
- [x] CTA/comment-trigger helper implemented.
- [x] Package integration paths documented or implemented.
- [x] P25 validation tests added.
- [x] P25 wildcard included in P1 Acceptance Harness.

## Downstream handoff checklist

- [x] P26 receives rights and monetization work as remaining gap.
- [x] P27 receives platform export work as remaining gap.
- [x] P28 receives long-form and topic intelligence work as remaining gap.
- [x] P29 receives editorial governance work as remaining gap.

## Guardrails confirmed

- [x] No misleading clickbait.
- [x] No unsupported claims.
- [x] No fabricated football facts.
- [x] No fake injury framing.
- [x] No fake scandal framing.
- [x] No automatic title approval.
- [x] No automatic visual approval.
- [x] No automatic retention approval.
- [x] No automatic CTA approval.
- [x] No automatic upload.
- [x] No automatic publishing.
- [x] No automatic monetization approval.
- [x] No automatic rights clearance.
- [x] No automatic editorial approval.
- [x] No YouTube API A/B testing.
- [x] No YouTube Analytics ingestion.
- [x] No comment scraping.
- [x] No comment posting.
- [x] No workflow gate bypass.
- [x] No implementation without scoped issue and PR.
- [x] No merge without exact-head CI.

## Closeout condition

P25 may close only after:

1. the final closeout PR number is patched into this checklist, the readiness report, and the final validation test;
2. all three required checks pass on the exact current PR head SHA;
3. the final closeout PR merges;
4. #343 is confirmed closed;
5. parent epic #327 is updated with final closeout evidence;
6. parent epic #327 is closed as completed.
