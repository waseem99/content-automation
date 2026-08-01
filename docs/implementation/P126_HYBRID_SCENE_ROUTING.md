# P126 Hybrid Scene Routing

## Outcome

P126 consumes an immutable `ready-for-final-video-generation/v1` package and creates an exact, explainable scene route plan. It does not contact a renderer, spend money, generate video or publish content.

## Route order

1. approved reusable asset/template;
2. deterministic composition;
3. local generation;
4. cloud-portable workflow;
5. low-cost premium renderer;
6. premium hero renderer;
7. manual edit.

The provider name is never treated as permanently best. Candidates are evaluated from active, versioned template, renderer catalogue, local-workflow and measurement evidence.

## Required evidence

Every planned scene retains:

- exact start, end and duration;
- continuity group and bindings;
- keyframe requirements;
- motion intensity and quality floor;
- selected route and all ranked fallbacks;
- measured or default acceptance rate;
- cost per accepted second and estimated scene cost;
- p50 ETA, deadline result and hardware availability;
- territory, quality and continuity checks;
- weighted score and rejection reasons.

## Spend controls

Paid candidates may be listed as explanations or fallbacks, but they cannot create an attempt unless all of the following are true:

- an active monthly `production_budget_policy` matches the content;
- the active hybrid policy allows a positive scene/content ceiling;
- an Admin records an explicit `hybrid_spend_approvals` approval;
- the approval ceiling covers the plan and remains inside monthly/content limits;
- any required lower-cost local route has been exhausted;
- the unique billing key has not been used for another scene/candidate.

`HYBRID_PAID_EXECUTION_ENABLED=false` remains the deployment default. Attempt creation records a planned attempt only; no provider request or generation job is submitted.

## Retry and fallback

A terminal failure advances the scene to the next eligible candidate in the immutable fallback chain. Billing keys are globally unique and idempotent. Terminal attempt rows cannot be edited or deleted.

## Reporting

The plan report separates:

- finished seconds;
- accepted generated seconds;
- retry seconds;
- accepted local, cloud and premium seconds;
- deterministic/reused seconds;
- manual-edit seconds;
- planned route seconds;
- actual recorded cost.

These are orchestration records, not renderer-throughput claims.

## Acceptance lifecycle

The P126 CI lifecycle creates one exact 120-second package with four 30-second scenes and proves:

- a reusable opening route;
- deterministic default routes;
- an audited manual override;
- an idempotent attempt replay;
- one failed deterministic attempt and fallback to manual edit;
- five terminal attempts completing all 120 seconds;
- 30 retry seconds;
- zero cloud/premium attempts;
- zero generation jobs;
- zero paid spend and no publishing.
