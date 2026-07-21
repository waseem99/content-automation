# P88 Local Concept Generation and Monthly Slates

## Safety boundary

Concept generation is review-only. A generation request creates a batch and candidate records; it does not create monthly plan items or `portfolio_content` rows.

The default adapter is deterministic and seed-bound. The optional model adapter accepts loopback endpoints only. No paid-provider path is available through the P88 API or Studio.

## Review flow

1. A producer generates candidates for one brand, month, requested format mix, pillar mix, count, and fixed seed.
2. Every candidate stores title, hook, concept, rationale, research needs, source needs, factual risk, complexity, estimated cost, route, duplicate evidence, score factors, and generation evidence.
3. Exact duplicates are always blocked. Historical semantic matches use a strict threshold; same-batch matches use a higher threshold to avoid treating ordinary brand vocabulary as duplication.
4. A reviewer shortlists, rejects, or restores candidates. Producers revise by creating a new immutable candidate; the prior candidate becomes superseded.
5. A reviewer builds a deterministic slate. Approval requires the exact requested candidate count, format distribution, pillar distribution, and no unresolved gaps.
6. Only an administrator can apply an approved slate, and only to a draft plan for the same brand and month.

## Application checks

Plan application runs in one PostgreSQL transaction and rechecks:

- slate status and batch status;
- exact selected candidate membership;
- shortlisted candidate status;
- unique schedule dates inside the target month;
- draft plan status, brand, month, and remaining capacity;
- current exact and semantic duplicates against brand history;
- one-time slate-item application evidence;
- candidate acceptance evidence and pinned brand-profile version.

Approved slate membership and distributions cannot be rewritten. Applied candidates, slate items, and slates cannot be reopened.

## Roles

- Producer: generate and revise candidates for assigned brands.
- Reviewer: shortlist, reject, restore, build slates, and approve slates for assigned brands.
- Administrator: all portfolio visibility and the final manual application to a draft monthly plan.

The Studio exposes deterministic generation only. It asks for a draft plan UUID and schedule start before administrator application; there is no automatic plan insertion.
