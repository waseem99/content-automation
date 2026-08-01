# Database-native campaigns and pre-generation autopilot

P119 establishes Creator Studio as the only production operating system for campaign planning and pre-generation preparation.

## Locked operating boundaries

- PostgreSQL is the only source of truth for campaign state, content identity, workflow status, evidence, decisions and lineage.
- Do not create or maintain an Excel, CSV or Google Sheets production tracker.
- Active files may remain on the local system and may have an optional Google Drive copy.
- Google Drive locations are file locations only. Drive folders and filenames never determine workflow state.
- Routine work progresses automatically up to `ready_for_final_video_generation` when the active brand policy passes.
- Final rendering, paid generation and public publishing remain separate controlled stages.

## First-slice workflow

```text
create campaign
→ add or edit campaign items in Creator Studio
→ validate campaign version
→ correct grouped validation errors
→ activate campaign version
→ automatic pre-generation orchestration in later P121/P122 slices
→ immutable pre-generation package
→ ready for final video generation
```

## Campaign records

A campaign belongs to one brand and has immutable versions. A version pins the active pre-generation autopilot policy and contains canonical campaign items.

Each item records:

- stable item key;
- title and topic;
- objective and audience;
- master format and duration;
- primary and target platforms;
- short-cut count;
- language and schedule;
- priority;
- canonical fingerprint;
- validation state and errors;
- linked content-family IDs once expanded;
- automatic disposition and readiness state.

## Default autopilot policy

Creating the first campaign for a brand creates an active `default-autopilot` policy when none exists.

The default automatically covers:

1. concept normalization;
2. script preparation;
3. sources;
4. narration planning;
5. scene planning;
6. captions and platform packaging;
7. final-generation package preparation.

Default hard blocks remain:

- rights;
- safety;
- territory;
- structural integrity;
- required source failure;
- budget;
- system failure.

The default policy does not authorize paid spend or public publishing.

## API foundation

```text
POST /p119/campaigns
GET  /p119/campaigns
GET  /p119/campaigns/{campaign_id}
POST /p119/campaign-versions/{campaign_version_id}/items
POST /p119/campaign-versions/{campaign_version_id}/validate
POST /p119/campaign-versions/{campaign_version_id}/activate
GET  /p119/brands/{brand_id}/autopilot-policy
POST /p119/brands/{brand_id}/autopilot-policy
```

Campaign item intake supports up to 10,000 items per validated request. Reusing the same campaign key or item key is idempotent when identity remains compatible.

## Storage records

`asset_storage_locations` permits only:

- `local`;
- `google_drive`.

The canonical asset remains the existing database asset record. Storage locations contain the physical locator, checksum, size and availability state.

## What this slice does not yet do

This foundation does not yet:

- expand active campaign items into all existing portfolio/workflow records;
- run the AI checks and bounded corrections;
- create grouped exception workspaces;
- generate final pre-generation packages;
- render final videos.

Those capabilities are delivered incrementally through P121, P122, P124 and the later hybrid-generation workstream. Existing single-item Creator Studio workflows remain available while the campaign path is completed.
