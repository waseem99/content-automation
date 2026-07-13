# P68 Step 02

This step implements the cross-platform direct-video ingestion and adaptive-sampling contract.

Part of #714. Closes #716 after the PR merges.

## Outcome

The reference engine now distinguishes a direct video/post URL from a profile, channel, page, or platform home URL before invoking yt-dlp.

Supported direct-input contracts:

- Facebook reel, watch, video, or `fb.watch` URL;
- YouTube watch, Shorts, live, or `youtu.be` URL;
- Instagram reel, reels, TV, or post URL;
- TikTok video URL;
- X/Twitter status URL.

The acceptance matrix is stored at:

```text
reference-engine/pilots/p68-cross-platform-acceptance.json
```

## Honest live-validation status

Facebook has one real direct-reel success from P67 workflow run `29146959999`.

YouTube, Instagram, TikTok, and X direct-video handling is contract-tested offline. Each still requires an operator-supplied authorized public example before its `live_status` may be changed from `operator_reference_required`.

The system must not claim that a platform has passed live acceptance merely because its URL format is recognized.

## Safe fallback

When a platform extractor cannot access an authorized video:

1. Record the exact extractor failure.
2. Do not bypass access controls.
3. Obtain the file through an authorized/operator-owned route.
4. Run `refintel ingest-file` with the applicable rights declaration.

Local `--cookies-from-browser` is available only for an operator-owned browser session. The browser name, cookies, and session data are never stored in project metadata, logs, artifacts, or the repository.

## Adaptive evidence sampling

The previous 60-second default produced only one interval frame for a short reel. P68 now selects interval density from measured duration:

| Reference duration | Interval |
| --- | ---: |
| up to 15 seconds | 2 seconds |
| 15–45 seconds | 3 seconds |
| 45–90 seconds | 5 seconds |
| 90–180 seconds | 10 seconds |
| 3–10 minutes | 30 seconds |
| over 10 minutes | 60 seconds |

Scene detection runs separately and adds scene midpoint frames. A fixed interval remains available through `--interval` for controlled comparisons.

The frame manifest records:

- adaptive or fixed mode;
- resolved interval;
- measured duration;
- scene-detection status.

## Boundaries

This step does not:

- crawl platform profiles or pages;
- discover every video owned by an account;
- solve CAPTCHAs;
- bypass private accounts, login walls, paywalls, or DRM;
- upload or log cookies;
- retain source media outside the temporary local workspace;
- republish source media;
- run final multimodal interpretation;
- generate or stitch production clips;
- deploy processing to Vercel;
- automatically approve or publish content.

P68-03 remains responsible for transcription, OCR, vision observations, shot taxonomy, emotional beats, caption rhythm, audio cues, and confidence-aware analysis.

