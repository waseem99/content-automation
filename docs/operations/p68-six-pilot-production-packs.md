# P68 Six-Pilot Production Packs

The P68 benchmark roster now contains three original Rawr Nation concepts and
three original Animal X concepts:

| Brand | Pilot | Visual mechanism |
| --- | --- | --- |
| Rawr Nation | `rawr-blind-spot` | Macro eye-to-retina demonstration |
| Rawr Nation | `rawr-gecko-grip` | Wildlife macro-to-microscopy scale shift |
| Rawr Nation | `rawr-archerfish-aim` | Split-level optics and high-speed water jet |
| Animal X | `animal-elephant-signals` | Behavior-led seismic communication |
| Animal X | `animal-prairie-dog-alarm` | Colony warning behavior across one location |
| Animal X | `animal-octopus-arms` | Arm-led exploration and distributed control |

Each directory under `p68-pilots/` contains a source brief, original script,
six-shot continuity plan, storyboard, clip prompts, narration project, and SRT
captions. All concepts use a locked subject, environment, light, color treatment,
screen direction, camera language, entry/exit actions, audio bridge, and at least
0.5 seconds of transition handle per planned clip.

Run the deterministic offline preparation and validation with:

```bash
PYTHONPATH=. python scripts/p68_prepare_gold_pilots.py
PYTHONPATH=. python scripts/p68_validate_six_pilots.py
```

`spec_ready` means only that the production pack is complete and internally
valid. It does not mean a preview or natural-motion clip exists. It cannot set
`natural_motion_ready`, `human_review_ready`, `production_candidate`, or
`publish_allowed`.

The next gate is natural-motion generation or licensed footage selection for
every unauthored shot, followed by continuity assembly, technical QA, benchmark
scoring, and human review. Static-plate motion remains preview-only. No Vercel
deployment is required for this offline media phase.
