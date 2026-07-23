from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_onboarding_never_reads_or_stores_operator_keys() -> None:
    source = (ROOT / "src/operations/local_onboarding.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "OPERATOR_API_KEYS_JSON" not in source
    assert "operator_keys_stored_in_database" in source
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and "api_key" in node.value.lower()
        for node in ast.walk(tree)
    )


def test_onboarding_seeds_exact_pilot_brands_and_roles() -> None:
    source = (ROOT / "src/operations/local_onboarding.py").read_text(encoding="utf-8")
    for value in ("rawr-nation", "animal-x", "admin", "producer", "reviewer", "publisher"):
        assert value in source
    assert "managed_renderer_enabled" in source
    assert "live_publishing_enabled" in source
