# P25 Step 01

This step defines the YouTube hook and retention scoring rubric for football Shorts and explainers.

Part of #327. Closes #338 after the PR merges.

## Goal

Create a clear, deterministic rubric for judging whether a generated Short or explainer can stop the scroll, explain the promise quickly, sustain attention, avoid generic narration, and trigger meaningful football comments before later automated or assisted scoring is implemented.

## Source references

This rubric builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p24-step-03.md
docs/operations/p24-step-05.md
src/content_package.py
.github/workflows/p1-acceptance-harness.yml
```

## Rubric status

This rubric is documentation-only.

It does not:

- generate titles;
- generate thumbnails;
- generate first-frame images;
- generate videos;
- score retention automatically;
- call AI scoring services;
- call YouTube analytics;
- upload to YouTube;
- publish content;
- approve monetization;
- approve rights;
- approve editorial status;
- bypass workflow gates.

## Score scale

Use the same 0 to 10 scale across every scoring dimension.

| Score | Label | Meaning |
| --- | --- | --- |
| 0-2 | `weak` | The segment is vague, slow, generic, or unlikely to hold attention. |
| 3-4 | `needs_revision` | The idea is understandable but lacks urgency, specificity, or visual force. |
| 5-6 | `usable_with_risk` | The segment can work, but it may lose viewers without stronger pacing or stakes. |
| 7-8 | `strong` | The segment is specific, visual, emotionally clear, and likely to retain attention. |
| 9-10 | `excellent` | The segment creates immediate curiosity, clear stakes, fast pacing, and strong comment potential. |

## Required scoring dimensions

Every future retention review should score these dimensions:

| Dimension | Required check |
| --- | --- |
| `first_1s_thumb_stop` | Does the first frame or first second create an immediate visual interruption? |
| `first_3s_clarity` | Does the viewer understand the topic, subject, and promise within three seconds? |
| `first_8s_retention_lock` | Does the first eight seconds create a clear open loop that makes viewers stay? |
| `curiosity_gap` | Is there a specific unanswered question that the viewer wants resolved? |
| `visual_interruption` | Does the edit pattern break monotony with motion, zoom, freeze-frame, stat card, or contrast? |
| `emotional_stakes` | Is the emotional reason to care obvious: legacy, rivalry, injury, pressure, comeback, or controversy? |
| `midpoint_reset` | Does the middle of the video introduce a new beat, question, comparison, or visual reset? |
| `cta_comment_trigger` | Does the ending ask a debate, prediction, ranking, loyalty, or versus question? |
| `dead_air_risk` | Does any segment feel slow, repetitive, or visually empty? |
| `genericness_risk` | Could the narration apply to any football player instead of this specific story? |

## First 1 second criteria

The first 1 second should answer:

- Who or what is visually on screen?
- Is there immediate movement, contrast, freeze-frame, impact, emotion, or pattern break?
- Can the viewer understand why to pause scrolling without needing context?
- Is the visual strong enough even with sound off?

High-scoring first 1 second examples:

- freeze-frame on a tackle with a bold caption;
- close-up reaction after a missed chance;
- split-screen of two rival players;
- stat-card shock number;
- crowd or player emotion with immediate zoom.

Low-scoring first 1 second examples:

- slow generic stadium shot;
- plain AI portrait with no context;
- unclear match footage;
- long intro branding;
- text that says only “football story.”

## First 3 seconds criteria

The first 3 seconds should answer:

- Which football person, team, or event is this about?
- What is the promise of the video?
- Why does it matter now?
- What question will the viewer want answered?

Strong 3-second structure:

```text
Visual interruption + specific subject + clear stakes
```

Example:

```text
This tackle changed Neymar's World Cup forever.
```

## First 8 seconds criteria

The first 8 seconds should lock retention by adding:

- the central question;
- a reason the story matters;
- one surprising or emotionally loaded detail;
- a transition into the main evidence or explanation.

A weak first 8 seconds explains background too early.

A strong first 8 seconds delays background until after the viewer understands the stakes.

## Midpoint reset criteria

The midpoint reset should prevent the video from feeling like a flat narration track.

Acceptable midpoint reset types:

- new question;
- player comparison;
- timeline jump;
- stat card;
- match-context switch;
- quote/comment overlay;
- visual pattern change;
- “but then” turn;
- scoreline or tournament pressure reveal.

A video should not run from hook to ending with the same image style, same pacing, and same sentence rhythm.

## Final CTA/comment-trigger criteria

The final CTA should create a useful football conversation.

CTA types:

- debate;
- prediction;
- ranking;
- loyalty;
- legacy;
- rivalry;
- versus;
- pressure question.

Strong CTA examples:

- “Be honest: is this Messi’s last real World Cup moment?”
- “Who carries more pressure in 2026: Mbappe or Messi?”
- “Rank these four by pressure, not talent.”
- “Was Neymar robbed of the legacy people expected?”

Weak CTA examples:

- “What do you think?”
- “Follow for more.”
- “Do you like football?”
- “Comment below.”

## Football hook examples

| Weak hook | Strong hook | Why the strong version works |
| --- | --- | --- |
| “Neymar was injured in 2014.” | “This tackle changed Neymar’s World Cup forever.” | Specific event, visual moment, consequence. |
| “Messi is old now.” | “Messi may have one last World Cup question to answer.” | Legacy stakes without insult or generic age framing. |
| “Mbappe is very fast.” | “Mbappe is chasing a record most legends never touched.” | Record chase creates curiosity and status. |
| “Yamal is a young player.” | “Yamal is carrying pressure most teenagers never survive.” | Emotional stakes and age-specific tension. |
| “Brazil had a bad game.” | “Brazil’s World Cup broke in one brutal sequence.” | Visual promise and dramatic event framing. |

## Future retention_score.json contract

Future P25 work should produce a `retention_score.json` or equivalent package section with:

- `hook_score`;
- `first_1s_thumb_stop_score`;
- `first_3s_clarity_score`;
- `first_8s_retention_lock_score`;
- `curiosity_gap_score`;
- `visual_pacing_score`;
- `emotional_stakes_score`;
- `midpoint_reset_score`;
- `cta_strength_score`;
- `dead_air_risk`;
- `genericness_risk`;
- `recommended_fixes`;
- `status`;
- `planned_epic`.

Initial status should remain `pending_p25` until an actual report is generated.

## Recommended fixes library

Common recommendations should include:

- open with the visual incident instead of background context;
- replace a generic claim with a specific football moment;
- add a comparison or stat card before the midpoint;
- shorten the intro voiceover;
- add a stronger first-frame caption;
- replace “what do you think” with a debate question;
- move factual context after the curiosity gap;
- add a visual reset before viewer fatigue.

## Guardrails

- No misleading clickbait.
- No unsupported claims.
- No fabricated football facts.
- No harassment of players, teams, fans, or communities.
- No implying injury, scandal, or controversy without source support.
- No publish approval from a retention score.
- No monetization approval from a retention score.
- No rights clearance from a retention score.
- No automatic upload.
- No automatic publishing.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p25_step_01.py
```

The validation checks scoring dimensions, score scale, first 1 second, first 3 seconds, first 8 seconds, midpoint reset, final CTA criteria, football-specific examples, future `retention_score.json` fields, guardrails, and P25 CI wildcard coverage.
