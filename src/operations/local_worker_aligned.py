from __future__ import annotations

import os

from src.operations.local_audio_alignment_patch import apply_local_audio_alignment_patch


# P105 retired the old public local-producer account. Preserve compatibility with
# existing .env.local files by routing the supervised local worker through the
# active Reviewer capability unless an explicit worker identity is configured.
if os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer") == "local-producer":
    os.environ["LOCAL_PRODUCER_OPERATOR_ID"] = os.getenv("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer")

apply_local_audio_alignment_patch()

from src.operations.local_worker_v2 import AlwaysOnLocalGenerationWorker, main  # noqa: E402
from src.operator_api.p111_runtime_patch import install_p111_worker_evidence_patch  # noqa: E402

install_p111_worker_evidence_patch(AlwaysOnLocalGenerationWorker)


if __name__ == "__main__":
    raise SystemExit(main())
