#!/usr/bin/env bash
set -euo pipefail

checkpoint="${P68_KEYFRAME_CHECKPOINT:-}"
if [[ -z "${checkpoint}" ]]; then
  echo "P68_KEYFRAME_CHECKPOINT is required." >&2
  exit 64
fi

checkpoint_path="/opt/ComfyUI/models/checkpoints/${checkpoint}"
if [[ ! -s "${checkpoint_path}" ]]; then
  echo "Required preview checkpoint is missing: ${checkpoint_path}" >&2
  exit 78
fi

exec python3 main.py \
  --listen "${COMFYUI_LISTEN:-0.0.0.0}" \
  --port "${COMFYUI_PORT:-8188}" \
  --disable-auto-launch \
  ${COMFYUI_EXTRA_ARGS:---lowvram}
