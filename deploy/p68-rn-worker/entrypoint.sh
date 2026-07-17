#!/usr/bin/env bash
set -euo pipefail

required=(
  "models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
  "models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
  "models/vae/wan2.2_vae.safetensors"
)

for model in "${required[@]}"; do
  if [[ ! -s "/opt/ComfyUI/${model}" ]]; then
    echo "Required Wan model is missing: ${model}" >&2
    exit 78
  fi
done

exec python3 main.py \
  --listen "${COMFYUI_LISTEN:-0.0.0.0}" \
  --port "${COMFYUI_PORT:-8188}" \
  --disable-auto-launch \
  ${COMFYUI_EXTRA_ARGS:-}
