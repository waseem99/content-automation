# P2 Readiness Report

## Scope

P2 is the source ingestion, research, and editorial intelligence layer for the football brief pipeline.

Completed flow:

```text
Intake -> Research Packet -> Editorial Review -> Draft Output -> Step Plan -> Operator Review Tools
```

## Completed issues and PRs

| Issue | Scope | PR | Status |
|---|---|---:|---|
| #35 | Source intake and topic input | #41 | Merged |
| #36 | Research packet worker | #42 | Merged |
| #37 | Editorial review prerequisites | #43 | Merged |
| #38 | Draft output worker | #44 | Merged |
| #39 | Step plan worker | #45 | Merged |
| #40 | Operator review tools | #46 | Merged |

## Current capabilities

- Operator can create controlled football intake records from topic, source URL, or both.
- Intake records are canonicalized, hashed, and deduplicated per workflow run.
- Research packet generation uses the worker execution layer and persists packet metadata, claims, citations, freshness, and confidence notes.
- Packet review is required before draft output generation.
- Draft outputs are structured with title, hook, outline, narration, citation map, metadata, and review-required status.
- Output review is required before step planning.
- Step plans create planning-only scenes, requirements, notes, and metadata.
- Operator tools expose queue, packet approval, output review request, and output approval commands.

## Operator commands

```bash
python -m src.infrastructure.database.cli intake create --workflow-run-id <id> --topic "Derby preview" --url https://example.com/story --json
python -m src.infrastructure.database.cli intake list --workflow-run-id <id> --json
python -m src.infrastructure.database.cli operator queue --workflow-run-id <id> --json
python -m src.infrastructure.database.cli operator approve-packet --workflow-run-id <id> --packet-id <id> --reviewed-by <name>
python -m src.infrastructure.database.cli operator request-output --workflow-run-id <id> --source-output-id <id>
python -m src.infrastructure.database.cli operator approve-output --workflow-run-id <id> --source-output-id <id> --reviewed-by <name>
```

## Ready for pilot

- End-to-end database-backed P2 smoke path.
- Manual source intake.
- Deterministic packet, draft output, and step plan generation for testable pipeline flow.
- Review gates before each downstream step.
- Operator queue visibility for pending review items.
- CI coverage through the P1 Acceptance Harness.

## Not production-ready yet

- Automated external content retrieval.
- Live source scraping or media downloading.
- Final asset approval and rights clearance workflow.
- Rendering, export, publishing, or scheduling.
- Full UI for operator review.
- Production observability dashboards.

## Recommended next phase

P3 should focus on production content assembly:

1. Approved asset and rights selection.
2. Render/package preparation.
3. Final approval gate.
4. Export or publishing manifest.
5. Operational UI or API surface for non-CLI users.
