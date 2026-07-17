# P68 local preview operator checklist

Before setup:

- Docker Desktop is running.
- Docker can access the NVIDIA GTX 1080.
- At least 12 GB is free on the selected data drive.
- The SDXL model licence has been reviewed by the operator.

Setup acceptance:

- checkpoint download occurs only with `-AcceptModelLicense`;
- downloaded checkpoint SHA256 matches the pinned value;
- ComfyUI is checked out at the pinned commit;
- service binds only to `127.0.0.1:8188`;
- local environment and media remain outside Git;
- no keyframe is generated during setup.

First sample acceptance:

- exactly one request is planned and submitted;
- pilot is `animal-octopus-arms` and shot is `S01` unless explicitly overridden;
- canvas is 704×1280;
- estimated and actual external spend remain USD 0.0000;
- output provenance is recorded;
- status is `pending_keyframe_review`;
- approval and publication remain false.
