# Verified GTX 1080 runtime

The local operator verified the following Docker image on the target Windows/Docker Desktop host:

- image: `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`
- GPU: NVIDIA GeForce GTX 1080
- CUDA available: true
- compiled architecture list includes `sm_61`

The P68 local preview worker therefore uses this exact image as its base rather than installing a different PyTorch wheel during the Docker build.

Review and publication boundaries remain unchanged:

- local loopback access only
- one 704x1280 sample by default
- generated output remains pending human review
- no automatic approval or publication
