FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

ARG COMFYUI_REF
RUN test -n "$COMFYUI_REF"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMFYUI_HOME=/opt/ComfyUI

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN python - <<'PY'
import torch
assert torch.__version__.startswith("2.0.1"), torch.__version__
print("Verified pinned base Torch:", torch.__version__)
PY

RUN printf '%s\n' \
      'torch==2.0.1' \
      'torchvision==0.15.2' \
      'torchaudio==2.0.2' \
      'numpy<2' \
      > /tmp/p68-runtime-constraints.txt

RUN git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_HOME" \
    && cd "$COMFYUI_HOME" \
    && git checkout "$COMFYUI_REF" \
    && test "$(git describe --tags --exact-match)" = "$COMFYUI_REF" \
    && if grep -Eq '^comfy-(aimdo|kitchen)' requirements.txt; then echo 'Unsupported modern ComfyUI dependency detected.' >&2; exit 1; fi \
    && if grep -R -n 'comfy_aimdo' main.py execution.py comfy 2>/dev/null; then echo 'Unsupported dynamic-VRAM import detected.' >&2; exit 1; fi \
    && grep -Ev '^(torch|torchvision|torchaudio|comfyui-frontend-package)([<=>].*)?$' requirements.txt > /tmp/comfyui-requirements-legacy.txt \
    && python -m pip install -c /tmp/p68-runtime-constraints.txt -r /tmp/comfyui-requirements-legacy.txt \
    && python -m pip install comfyui-frontend-package==1.12.8 cmake lit \
    && python -m pip check

RUN python - <<'PY'
import importlib.metadata
import torch
assert torch.__version__.startswith("2.0.1"), torch.__version__
assert importlib.metadata.version("comfyui-frontend-package") == "1.12.8"
print("Verified pinned Torch after dependencies:", torch.__version__)
print("Verified compatible frontend:", importlib.metadata.version("comfyui-frontend-package"))
PY

COPY entrypoint.sh /usr/local/bin/p68-local-keyframe-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/p68-local-keyframe-entrypoint \
    && chmod 0755 /usr/local/bin/p68-local-keyframe-entrypoint \
    && test "$(head -n 1 /usr/local/bin/p68-local-keyframe-entrypoint)" = '#!/usr/bin/env bash'

WORKDIR /opt/ComfyUI
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=10 \
    CMD curl --fail --silent http://127.0.0.1:8188/system_stats >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/p68-local-keyframe-entrypoint"]
