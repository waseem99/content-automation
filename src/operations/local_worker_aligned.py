from __future__ import annotations

from src.operations.local_audio_alignment_patch import apply_local_audio_alignment_patch


apply_local_audio_alignment_patch()

from src.operations.local_worker_v2 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
