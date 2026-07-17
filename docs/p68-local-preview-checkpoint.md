# P68 local preview checkpoint

## Verified host

- Windows Docker Desktop with WSL 2
- NVIDIA GeForce GTX 1080
- 8192 MiB VRAM visible inside a CUDA 12.4 container
- local storage root: `D:\content-automation-data\p68-keyframe-worker`

## Preview execution policy

- local loopback worker only
- SDXL Base 1.0 checkpoint download requires explicit local licence acceptance
- checkpoint revision and SHA256 are pinned
- 704×1280 low-VRAM canvas
- one generation request per sample run
- USD 0.0000 local cost ledger
- outputs remain outside Git
- completed output status is `pending_keyframe_review`
- human approval is separate
- video generation and publishing remain disabled

## First sample target

- pilot: `animal-octopus-arms`
- shot: `S01`
- route: local ComfyUI keyframe preview
- next gate after successful generation: human anatomy, continuity, composition, rights, and prompt-fit review
