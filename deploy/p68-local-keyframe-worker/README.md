# P68 local keyframe preview worker

This worker uses the Windows PC's NVIDIA GPU through Docker Desktop to create review-only P68 keyframe samples. It is intentionally separate from the Wan natural-video worker.

## Scope

- local loopback access only
- one bounded sample shot by default
- 704×1280 portrait preview canvas for the GTX 1080 8 GB profile
- zero external-provider cost
- generated images remain outside Git
- every completed image enters `pending_keyframe_review`
- no automatic keyframe approval
- no video generation
- no deployment or publication

## Pinned components

- ComfyUI release: `v0.3.26`
- PyTorch base image: `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`
- torchvision: `0.15.2`
- torchaudio: `2.0.2`
- required compiled GPU architecture: `sm_61`
- checkpoint: `stabilityai/stable-diffusion-xl-base-1.0/sd_xl_base_1.0.safetensors`
- checkpoint revision: `a7c2bcc30a3b5489f1f1989e66cd5fe957fdb45c`
- checkpoint SHA256: `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b`
- model licence: CreativeML Open RAIL++-M

ComfyUI `v0.3.26` is intentionally used because it supports the SDXL workflow required here but predates the mandatory `comfy-aimdo` and `comfy-kitchen` packages that require a newer PyTorch/CUDA generation than the GTX 1080-compatible runtime.

Container startup verifies CUDA availability, the detected GPU capability, and compatibility with the compiled architecture list. The Docker build also rejects a ComfyUI ref that introduces the unsupported dynamic-VRAM packages.

The setup script does not download the checkpoint unless the operator supplies `-AcceptModelLicense`. It records local licence evidence and verifies the complete checkpoint hash before starting the worker.

## Windows setup

From a checked-out repository branch containing this worker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_p68_local_keyframe_worker.ps1 `
  -AcceptModelLicense
```

The first execution downloads approximately 6.94 GB if the checkpoint is absent, builds the pinned Docker image, starts ComfyUI on `127.0.0.1:8188`, and stops without generating anything.

## One bounded sample

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\run_p68_local_keyframe_sample.ps1
```

Default sample:

- pilot: `animal-octopus-arms`
- shot: `S01`
- request limit: one
- canvas: 704×1280
- cost ledger: USD 0.0000

The script polls the local worker and prints the image path only after provenance intake succeeds. The image remains blocked from video generation until a separate human approval command is executed.

## Stop or restart

Use the environment file created outside Git:

```powershell
cd .\deploy\p68-local-keyframe-worker
docker compose --env-file D:\content-automation-data\p68-keyframe-worker\local-keyframe-worker.env down
docker compose --env-file D:\content-automation-data\p68-keyframe-worker\local-keyframe-worker.env up -d
```

Do not expose port 8188 beyond loopback and do not add the generated environment file, checkpoint, outputs, or artefacts to Git.
