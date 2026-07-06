# P2 Closeout Checklist

## Implementation

- [x] Source intake created and persisted.
- [x] Source intake supports topic-only, URL-backed, and combined inputs.
- [x] Intake canonical hash prevents duplicate work per workflow run.
- [x] Research packet is created from intake.
- [x] Packet output stores claims, citations, metadata, freshness, and confidence notes.
- [x] Packet review prerequisite is stored.
- [x] Packet approval is required before draft output generation.
- [x] Draft output is created from approved packet.
- [x] Draft output stores title, hook, outline, narration, citation map, metadata, and output hash.
- [x] Output review prerequisite is available.
- [x] Output approval is required before step planning.
- [x] Step plan is created from approved output.
- [x] Step plan stores scenes, requirements, notes, metadata, and output hash.
- [x] Operator queue surfaces pending packet reviews, output reviews, and plan reviews.
- [x] Operator commands can approve packet and output review items.

## Guardrails

- [x] Missing review blocks downstream work.
- [x] Pending review blocks downstream work.
- [x] Change-requested review blocks downstream work where applicable.
- [x] Duplicate worker requests reuse existing stage outputs.
- [x] Step plan does not attach third-party media.
- [x] Step plan requirements remain rights-review required.
- [x] Rendering and publishing are not introduced in P2.

## Validation

- [x] P2 end-to-end smoke test added.
- [x] P1 Acceptance Harness runs the P2 end-to-end smoke test.
- [ ] P1 Acceptance Harness green on the closeout PR head.
- [ ] P1 Foundation Closeout green on the closeout PR head.
- [ ] Closeout PR merged into `test`.

## Follow-up after merge

- [ ] Create P3 backlog.
- [ ] Define asset and rights selection model.
- [ ] Define final approval gate.
- [ ] Define export or publishing manifest.
