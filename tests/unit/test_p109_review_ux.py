from pathlib import Path

import pytest

from src.application.scripts import runtime_patch
from src.application.scripts.models import ScriptDecision
from src.application.scripts.service import ScriptReviewError


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "web" / "static-creator-ui" / "index.html"
REVIEW_UX = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-review-ux.js"


def test_optional_review_note_layer_is_loaded_after_main_studio() -> None:
    index = INDEX.read_text(encoding="utf-8")
    main = index.index('/assets/studio-v2.js')
    review = index.index('/assets/studio-v2-review-ux.js')

    assert review > main
    source = REVIEW_UX.read_text(encoding="utf-8")
    assert "Decision note (optional)" in source
    assert "a single word is enough" in source
    assert "sessionStorage.setItem" in source
    assert 'document.addEventListener("click", handleDecision, true)' in source
    assert "at least 10 characters" not in source


def test_blank_and_short_review_notes_are_normalized_for_existing_database_contract() -> None:
    assert runtime_patch._normalize_rationale(ScriptDecision.APPROVED, "") == "Approved"
    assert runtime_patch._normalize_rationale(ScriptDecision.CHANGES_REQUESTED, "  ") == "Changes requested"
    assert runtime_patch._normalize_rationale(ScriptDecision.REJECTED, "ok") == "ok."
    assert runtime_patch._normalize_rationale(ScriptDecision.APPROVED, "good") == "good"


def test_database_approval_gate_is_returned_as_a_friendly_blocker(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("Unsupported factual claims block script approval")

    monkeypatch.setattr(runtime_patch, "_ORIGINAL_DECIDE", fail)

    with pytest.raises(ScriptReviewError) as caught:
        runtime_patch._decide_with_friendly_validation(
            object(),
            document_id="document-id",
            expected_lock_version=2,
            decision=ScriptDecision.APPROVED,
            rationale="good",
            reviewer="local-super-admin",
        )

    assert caught.value.code == "script_decision_blocked"
    blocker = caught.value.details["blockers"][0]
    assert blocker["code"] == "unsupported_factual_claims"
    assert "supporting source" in blocker["message"]
