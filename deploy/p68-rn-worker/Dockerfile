FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG COMFYUI_REF
RUN test -n "$COMFYUI_REF"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMFYUI_HOME=/opt/ComfyUI

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ffmpeg python3 python3-pip ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_HOME" \
    && cd "$COMFYUI_HOME" \
    && git checkout "$COMFYUI_REF" \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install -r requirements.txt huggingface_hub

COPY entrypoint.sh /usr/local/bin/p68-rn-entrypoint
RUN chmod 0755 /usr/local/bin/p68-rn-entrypoint

WORKDIR /opt/ComfyUI
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD curl --fail --silent http://127.0.0.1:8188/system_stats >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/p68-rn-entrypoint"]
