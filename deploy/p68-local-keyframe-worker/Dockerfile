FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ARG COMFYUI_REF
RUN test -n "$COMFYUI_REF"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMFYUI_HOME=/opt/ComfyUI \
    P68_TORCH_VERSION=2.7.1 \
    P68_TORCHVISION_VERSION=0.22.1 \
    P68_TORCHAUDIO_VERSION=2.7.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ffmpeg python3 python3-pip ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_HOME" \
    && cd "$COMFYUI_HOME" \
    && git checkout "$COMFYUI_REF" \
    && python3 -m pip install --upgrade pip \
    && grep -Ev '^(torch|torchvision|torchaudio)([<=>].*)?$' requirements.txt > /tmp/comfyui-requirements-no-torch.txt \
    && python3 -m pip install -r /tmp/comfyui-requirements-no-torch.txt \
    && python3 -m pip install \
        "torch==${P68_TORCH_VERSION}" \
        "torchvision==${P68_TORCHVISION_VERSION}" \
        "torchaudio==${P68_TORCHAUDIO_VERSION}" \
        --index-url https://download.pytorch.org/whl/cu118 \
    && python3 - <<'PY'
import torch
assert torch.__version__.startswith("2.7.1"), torch.__version__
compiled_arches = torch.cuda.get_arch_list()
assert "sm_61" in compiled_arches, compiled_arches
print("Verified GTX 10-series runtime:", torch.__version__, compiled_arches)
PY

COPY entrypoint.sh /usr/local/bin/p68-local-keyframe-entrypoint
RUN chmod 0755 /usr/local/bin/p68-local-keyframe-entrypoint

WORKDIR /opt/ComfyUI
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=10 \
    CMD curl --fail --silent http://127.0.0.1:8188/system_stats >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/p68-local-keyframe-entrypoint"]
