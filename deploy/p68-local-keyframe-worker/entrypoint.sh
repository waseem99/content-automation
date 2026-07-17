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

python3 - <<'PY'
import sys
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable inside the local preview container.")
capability = torch.cuda.get_device_capability(0)
required_arch = f"sm_{capability[0]}{capability[1]}"
compiled_arches = torch.cuda.get_arch_list()
if required_arch not in compiled_arches:
    raise SystemExit(
        f"Installed PyTorch does not support GPU architecture {required_arch}; compiled arches: {compiled_arches}"
    )
if capability != (6, 1):
    print(f"Notice: validated host was sm_61, current GPU reports {capability}.", file=sys.stderr)
print(
    f"P68 local preview runtime verified: {torch.cuda.get_device_name(0)}, "
    f"capability={required_arch}, torch={torch.__version__}"
)
PY

exec python3 main.py \
  --listen "${COMFYUI_LISTEN:-0.0.0.0}" \
  --port "${COMFYUI_PORT:-8188}" \
  --disable-auto-launch \
  ${COMFYUI_EXTRA_ARGS:---lowvram}
