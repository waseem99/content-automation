# P55 Local Creator Demo Gallery

Part of #611. Closes #612–#617 after merge.

## What this builds

P55 generates several local P54 creator review workspaces and combines them into one browser-openable demo gallery.

This is intended for manual product review: the team can open one gallery page, inspect multiple generated content packs, and decide which ideas are good enough to move toward production.

## Inputs

A JSON file with a `briefs` list, for example:

```json
{
  "briefs": [
    {
      "demo_id": "ai-automation-founder-short",
      "topic": "AI automation for service business owners",
      "platform": "youtube_shorts",
      "audience": "small agency founders and service business owners",
      "monetization_goal": "generate qualified leads for an AI automation consulting offer"
    }
  ]
}
```

## Outputs

At the gallery output root:

- `index.html` — browser-openable demo gallery
- `demo_gallery.json` — structured gallery summary
- one generated P54 review workspace per demo brief

Each demo workspace includes:

- `index.html`
- `creator_review.json`
- `producer_brief.md`
- `script.txt`
- `storyboard.md`
- `shot_list.csv`
- `captions.srt`
- `metadata.json`
- `asset_manifest.json`
- `review_checklist.md`
- `platform_variants.json`

## Local command

```bash
python -m src.p55_creator_demo_gallery \
  docs/operations/p55-demo-briefs.json \
  --output-root outputs/demo-gallery \
  --overwrite
```

Then open:

```text
outputs/demo-gallery/index.html
```

## Demo library

The included demo library covers:

- AI automation consulting lead generation
- restaurant launch campaign
- fitness coach TikTok education
- SaaS onboarding longform content
- real estate buyer advisory content

## Review purpose

Use the gallery to judge:

- Which hooks are actually strong?
- Which scripts feel generic?
- Which storyboards are useful for editors?
- Which ideas are rights-safe enough?
- Which ideas feel monetizable?
- Which content pack should move toward production?

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or performance guarantee is introduced.

The gallery is local static HTML and local JSON/Markdown/TXT/CSV/SRT artifacts only.
