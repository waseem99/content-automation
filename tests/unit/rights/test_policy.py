from __future__ import annotations

import json

from src.application.rights.policy import canonical_json_bytes, load_rights_policy


def test_policy_hash_is_stable_for_equivalent_json(tmp_path) -> None:
    first = {
        "policy_name": "test",
        "version": "1",
        "reason_priority": ["A", "B"],
        "supported_platforms": ["youtube"],
        "review_due_behavior": "human_review_required",
    }
    second = {
        "review_due_behavior": "human_review_required",
        "supported_platforms": ["youtube"],
        "reason_priority": ["A", "B"],
        "version": "1",
        "policy_name": "test",
    }
    assert canonical_json_bytes(first) == canonical_json_bytes(second)

    path = tmp_path / "policy.json"
    path.write_text(json.dumps(first), encoding="utf-8")
    policy = load_rights_policy(path)
    assert policy.version == "1"
    assert len(policy.content_hash) == 64


def test_repository_policy_has_deterministic_reason_priority() -> None:
    policy = load_rights_policy(__import__("pathlib").Path("policies/rights-gate/v1.json"))
    assert policy.priority("ASSET_HASH_MISMATCH") < policy.priority("ATTRIBUTION_MISSING")
    assert set(policy.supported_platforms) == {
        "youtube",
        "facebook",
        "tiktok",
        "instagram",
    }
