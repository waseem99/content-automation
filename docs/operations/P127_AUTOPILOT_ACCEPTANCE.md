# P127 Automatic Pre-generation Acceptance

## Purpose

Measure the existing campaign, content-family, script, source, approval and immutable-package services at 1,000-item scale. This is not a synthetic row-state benchmark.

## Dataset

- 1,000 unique campaign items;
- one canonical master per item;
- one deterministic 45-second script per master;
- 950 scripts receive explicit government-source evidence for every factual claim;
- 50 scripts deliberately retain unsupported factual claims.

## Expected result

- 950 items reach `ready_for_final_video_generation` automatically;
- 50 items become non-waivable `source_block` hard blockers;
- the 50 blockers appear as one grouped exception using the same policy/rule version;
- zero human exceptions;
- zero individual item-page approvals;
- every ready item retains all five passed script checks and one passed `automatic_policy_decision` check;
- every ready script is approved by the non-login `pre-generation-autopilot-reviewer` identity;
- no video generation, provider request, paid spend or publishing occurs.

## Claim isolation

P127 adds an optional campaign filter to `PreGenerationService.claim`. Existing workers omit the filter and use the original claim implementation. Acceptance, recovery and campaign-specific operations can isolate one campaign without pausing unrelated work.

## Evidence

`autopilot_acceptance_runs` retains:

- requested, ready, blocked, human-exception and corrected counts;
- automation rate;
- grouped source-block count;
- content-family and script-document counts;
- reproducible automatic-decision count;
- exact timings and environment evidence;
- failure details when the acceptance gate does not pass.
