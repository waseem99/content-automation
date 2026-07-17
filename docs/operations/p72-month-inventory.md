# P72 month inventory and readiness

P72 turns the August 2026 portfolio plan into reviewable inventory without generating,
buying, or publishing media. Rawr Nation and Animal X each receive 24 differentiated
concepts: 19 short-form videos and five feature videos. All ideas remain at the `idea`
stage until a human approves the next gate.

Historiq and Ani Films are now identified and marked research-pending; no inventory is
invented for them before page analysis. The other three portfolio slots remain deliberately
blocked until their names, page links, audience positioning, and source policies are verified.

## Load the inventory

Start the private P71 staging stack, set `OPERATOR_KEY` in the shell, then run:

```bash
python scripts/p71_bootstrap_portfolio.py
```

The bootstrap upserts brands and plans, creates missing ideas, skips matching ideas on
subsequent runs, and prints the resulting readiness report. It makes no publish calls.

## Inspect readiness

```bash
curl -sS \
  -H "X-Operator-Key: $OPERATOR_KEY" \
  "http://127.0.0.1:8000/portfolio/readiness?month_start=2026-08-01"
```

For each active database brand the response reports its target, total planned inventory,
remaining gap, counts by workflow stage, onboarding status, and whether its inventory is
complete. A complete inventory is not an approval: scripts, evidence, voice, preview,
premium spend, packaging, and publishing retain their separate gates.

## Next production gate

Research and source the first six concepts per confirmed brand, then generate scripts and
voice drafts for human review. Do not purchase premium video renders until those scripts
and shot plans pass review. Do not activate the final three placeholder brands until
verified links and brand identities are provided.
