# P68 RN video worker

This package runs the open-source Wan 2.2 TI2V-5B workflow behind a headless ComfyUI API. It is a development and first-pass production worker; generated clips still require P68 quality, rights, and human review.

## Requirements

- Linux host with Docker, the NVIDIA container runtime, and a supported NVIDIA GPU.
- The Hugging Face `hf` CLI for the pinned model download step.
- Persistent storage for approximately model-sized downloads plus generated clips.
- A reviewed ComfyUI commit SHA supplied as `COMFYUI_REF`.
- Private networking, SSH forwarding, or an authenticated TLS reverse proxy. Do not expose raw ComfyUI directly to the public internet.

## Install

```bash
cp .env.example .env
# Set reviewed COMFYUI_REF, WAN22_REVISION, WAN21_REVISION commit SHAs,
# and absolute storage paths.
source .env
./download-models.sh "$RN_MODEL_DIR" "$WAN22_REVISION" "$WAN21_REVISION"
docker compose build
docker compose up -d
curl --fail http://127.0.0.1:${RN_COMFYUI_PORT}/system_stats
```

The downloader writes `p68-wan22-model-checksums.sha256`. Copy those digests into `model-manifest.json`, capture and hash the applicable license/terms, and approve the manifest before any output can become a production candidate.

The application uses `P68_RN_BASE_URL`, an optional proxy bearer token, and the API-format workflow in `workflows/wan22-ti2v-5b-api.json`. The official ComfyUI browser workflow was converted to API format and retains the native core nodes and model filenames.
