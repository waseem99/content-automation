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
compiled_arches = torch.cuda.get_arch_list()
assert "sm_61" in compiled_arches, compiled_arches
print("Verified GTX 1080 base runtime:", torch.__version__, compiled_arches)
PY

RUN git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_HOME" \
    && cd "$COMFYUI_HOME" \
    && git checkout "$COMFYUI_REF" \
    && grep -Ev '^(torch|torchvision|torchaudio)([<=>].*)?$' requirements.txt > /tmp/comfyui-requirements-no-torch.txt \
    && python -m pip install -r /tmp/comfyui-requirements-no-torch.txt \
    && python -m pip check

COPY entrypoint.sh /usr/local/bin/p68-local-keyframe-entrypoint
RUN chmod 0755 /usr/local/bin/p68-local-keyframe-entrypoint

WORKDIR /opt/ComfyUI
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=10 \
    CMD curl --fail --silent http://127.0.0.1:8188/system_stats >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/p68-local-keyframe-entrypoint"]
