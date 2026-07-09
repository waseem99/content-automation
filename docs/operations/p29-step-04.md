# P29 Step 04

Part of #331. Closes #365 after the batch PR merges.

## Goal

Clarify and enforce the difference between preview renders and publish-ready renders so operators do not confuse an assembled video with an approved publishing asset.

## Render modes

| Mode | Output name | Meaning |
| --- | --- | --- |
| `preview` | `preview_video.mp4` | Internal review render only. Not a publishing asset. |
| `publish` | `publish_video.mp4` | Export-ready render after approval gates pass. Still not a platform upload. |

## Publish render gating

Publish render is allowed only when the package has:

- approved package state;
- P26 risk clearance;
- P29 editorial approval;
- rights review clearance;
- `publish_export_ready` editorial status.

Preview render does not imply approval, publish readiness, or platform upload permission.

## README/code mismatch

The repo has used terms including:

- `final_video.mp4`
- `preview_video.mp4`
- `publish_video.mp4`

Recommended correction: use `preview_video.mp4` for internal review renders and `publish_video.mp4` only after `publish_export_ready`. Avoid treating `final_video.mp4` as approval.

## Example

```text
docs/operations/p29-render-rules-example.json
```

## Validation

```text
src/p29_governance.py
tests/integration/test_p29_batch_02_06.py
```

## Stop conditions

Stop if a future change attempts to:

- directly publish to platforms;
- rework the full video assembler in this step;
- treat preview renders as approved assets;
- treat publish renders as automatic upload permission;
- set `publish_allowed` to `true`;
- bypass P26/P29 gates.
