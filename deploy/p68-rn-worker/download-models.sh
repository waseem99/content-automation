#!/usr/bin/env bash
set -euo pipefail

target="${1:-/srv/p68-rn/models}"
wan22_revision="${2:-${WAN22_REVISION:-}}"
wan21_revision="${3:-${WAN21_REVISION:-}}"
if [[ -z "${wan22_revision}" || -z "${wan21_revision}" ]]; then
  echo "Pin WAN22_REVISION and WAN21_REVISION to reviewed Hugging Face commit SHAs." >&2
  exit 64
fi
mkdir -p "${target}/diffusion_models" "${target}/text_encoders" "${target}/vae"

hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
  --revision "${wan22_revision}" \
  --local-dir "${target}/.wan22"
hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/vae/wan2.2_vae.safetensors \
  --revision "${wan22_revision}" \
  --local-dir "${target}/.wan22"
hf download Comfy-Org/Wan_2.1_ComfyUI_repackaged \
  split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  --revision "${wan21_revision}" \
  --local-dir "${target}/.wan21"

cp "${target}/.wan22/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" "${target}/diffusion_models/"
cp "${target}/.wan22/split_files/vae/wan2.2_vae.safetensors" "${target}/vae/"
cp "${target}/.wan21/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" "${target}/text_encoders/"

sha256sum \
  "${target}/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" \
  "${target}/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
  "${target}/vae/wan2.2_vae.safetensors" \
  > "${target}/p68-wan22-model-checksums.sha256"
