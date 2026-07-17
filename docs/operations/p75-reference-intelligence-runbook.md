# P75 reference-intelligence operator runbook

## Boundary

Run acquisition and media analysis only on an operator-controlled machine. Never run FFmpeg,
browser authentication, extraction, transcription, local vision, or source-media storage on
Vercel. PostgreSQL and the hosted operator UI receive sanitized metadata, hashes, approval state,
and `reference://` locators only.

Process media only when it is owned, permitted, supplied by the rights holder, or lawfully
inspected as a public internal-research reference. Do not bypass private accounts, DRM, paywalls,
CAPTCHAs, signed-link restrictions, rate limits, or platform safeguards.

## Installation and environment check

```bash
cd reference-engine
python -m pip install -e '.[media,speech,browser,dev]'
playwright install chromium
refintel doctor
refintel capabilities
refintel profiles
```

Use environment variables for non-secret configuration and paths to local secret files. Never put
raw cookies, passwords, MFA values, or session tokens in environment files:

```bash
export REFINTEL_WORKSPACE=/absolute/local/path/reference-workspace
export REFINTEL_FACEBOOK_PROFILE=/absolute/local/path/facebook-browser
# Choose at most one authentication route when required:
export REFINTEL_COOKIES_FROM_BROWSER=chrome
# export REFINTEL_FACEBOOK_COOKIE_FILE=/absolute/local/path/cookies.txt
```

## Execution profiles

| Profile | Speech | Local vision | Every-frame metrics | Use |
|---|---|---:|---:|---|
| `cpu` | small model on CPU | No | Yes | Default complete deterministic run |
| `gpu` | medium model on CUDA | Yes | Yes | Higher-quality workstation run with local Ollama |
| `low-memory` | tiny model on CPU | No | No | Constrained-machine fallback |

The GPU profile requires CUDA and a locally running Ollama vision model. It does not call a hosted
vision service. If GPU prerequisites are unavailable, rerun with `--profile cpu`; do not silently
claim GPU or model evidence.

## Single reference

```bash
refintel run-reference /absolute/path/authorized-video.mp4 \
  --rights permitted \
  --profile cpu \
  --brand rawr-nation \
  --topic "A separately researched original topic"
```

For a Facebook page, one command performs discovery, verified acquisition, and analysis:

```bash
refintel facebook-page https://www.facebook.com/RawrNationTV \
  --brand rawr-nation \
  --rights public-internal-research \
  --limit 3 \
  --no-local-vision
```

Items are processed sequentially so one failure is isolated. A cached acquisition is reused only
when its successful manifest, primary file, size, and SHA-256 all verify. Failed or incomplete
cached acquisitions are retried automatically. The final summary reports `verified_media`
separately from `analyzed`; analysis cannot succeed without non-empty video evidence artifacts.

For a public direct-media URL, replace the file path with the URL. Profile/page inputs require
discovery first. Facebook share links require local resolution. If acquisition fails, obtain an
authorized local export and use the file command.

## Portfolio batch

Create a non-secret request template:

```bash
refintel init-portfolio-request --output reference-portfolio-request.json
```

Edit the request with one rights declaration per item, then run:

```bash
refintel run-portfolio reference-portfolio-request.json
```

The command is resumable through canonical source identity and existing artifacts. Each item fails
independently. The run manifest contains safe source labels, status, artifact counts, errors, and
local-upload fallbacks; it contains no source bytes, credentials, absolute paths, generation
approval, or publication instruction.

## Portfolio handoff and review

Each successful item writes `exports/portfolio_sync_packet.json`. Register the packet metadata
with the operator API, then inspect the database-backed reference queue. Review artifacts locally;
the hosted UI shows their types and hashes, not source media.

Record rights, originality, and editorial decisions explicitly. Rights and originality approvals
are required before linking research mechanics to a content idea. A gate decision never triggers
generation, paid rendering, scheduling, or publishing.

## Failure recovery

| Failure | Action |
|---|---|
| Unsupported profile/page input | Run discovery and supply direct public-media URLs |
| Login or extractor drift | Use an operator-owned local browser or authorized local export |
| Facebook session expired | Run `refintel facebook-login` locally and retry |
| Snapchat route unavailable | Use an authorized local export; profile discovery is unsupported |
| CUDA/Ollama unavailable | Rerun with `--profile cpu` |
| Transcript unavailable | Continue with an explicit limitation; never mark originality passed |
| Corrupt item in a batch | Fix or replace that item and rerun; other completed items remain reusable |
| Suspected secret/path leakage | Stop, delete the run artifact, rotate the affected session, and rerun |

## Acceptance and live probes

Offline acceptance is authoritative for adapters, redaction, rights, source-media isolation,
originality, resumability, per-item failures, and human review:

```bash
pytest -q tests/test_p75_acceptance.py tests/test_p75_orchestration.py
pytest -q
```

The P67 GitHub workflow performs the only automated controlled public Facebook probe. Other live
platform probes require a suitable operator-supplied public reference and must not be interpreted
as permanent platform support. Never place cookies or source media in CI artifacts.

## Completion checklist

- Rights declaration recorded for every item.
- Platform route and authentication limitation disclosed honestly.
- Measured, extracted, model-observed, and fallback evidence remain distinguishable.
- Still/slideshow-like material is not described as animated video.
- Source media, source wording, identities, branding, voices, and music are excluded from output.
- Originality and human review gates are complete before production.
- No Vercel media processing or automatic publication occurred.
